"""F-6 relay: deliver NT8 RiskGuard alerts to Discord (and optionally SMS).

WHY THIS IS A SEPARATE PROCESS.

The guard is an NT8 AddOn. It shares a process with the platform that manages real
positions, and a webhook POST from an NT8 callback thread can block on a slow or wedged
remote host. So the guard performs **no network I/O at all**: it DECIDES which events a
human should be told about (``GuardAlertSink``, mutation-tested in the nt8-riskguard repo)
and appends the decision to ``alerts_outbox.jsonl``. This process delivers them.

The second reason is reuse. ``scripts.libs_py.discord`` already carries Discord behaviour
that would otherwise have to be reimplemented in C# inside a trading platform:

  * a 1900-character cap rather than 2000, leaving margin for JSON code-point expansion
  * the ~5 msg / 2 s per-webhook rate limit
  * ``Retry-After`` read from the 429 header rather than guessed
  * capped exponential backoff on 429/5xx, and an embed-to-text fallback
  * delivery telemetry, because "logs to read but no aggregate counters" was already
    learned here once

⚠️ THE FAILURE MODE THIS DESIGN INTRODUCES, AND ITS ANSWER.

Moving delivery out of the guard means alerts vanish silently if this process is not
running -- and **silence is undetectable by definition**. You cannot notice the absence of
a message you were never going to get. This repo's most-repeated lesson is "an alarm that
is always on is off"; a relay nobody notices dying is the same defect wearing the opposite
sign.

So the relay emits a positive HEARTBEAT on a schedule. The operator's rule is then
inverted into something checkable: *if the heartbeat stops arriving, the channel is dead*.
A missing periodic message is noticeable in a way that a missing alert is not.

The heartbeat also reports the GUARD's own liveness, read from ``heartbeat.txt``, so the
two failures are distinguishable rather than merged:

    relay up   + guard fresh  -> normal
    relay up   + guard stale  -> NT8 or the addon is down, and you are told
    relay down                -> no heartbeat arrives at all, and you notice

⚠️ TELEGRAM IS DELIBERATELY NOT IMPLEMENTED, and is refused BY NAME rather than being
silently absent. Advertising a channel the receiver does not implement is `P1-72` in the
NT8 repos, which has now regressed twice.

Usage::

    python -m scripts.riskguard.alert_relay --channel test_channel
    python -m scripts.riskguard.alert_relay --channel test_channel --once
    python -m scripts.riskguard.alert_relay --channel alerts --sms-on-critical
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# The guard writes both of these into <NT8 UserDataDir>/RiskGuard/.
DEFAULT_GUARD_DIR = Path.home() / "Documents" / "NinjaTrader 8" / "RiskGuard"
OUTBOX_NAME = "alerts_outbox.jsonl"
HEARTBEAT_NAME = "heartbeat.txt"

# Where the relay remembers how far it has read. Kept BESIDE the outbox so a wiped guard
# directory resets both together and cannot leave a cursor pointing past a shorter file.
CURSOR_NAME = "alerts_relay_cursor.json"

DEFAULT_POLL_SECONDS = 5.0
DEFAULT_HEARTBEAT_MINUTES = 60
# The guard rewrites heartbeat.txt on every safety sweep, so minutes of silence means it
# is not running -- not that the market is quiet.
GUARD_STALE_AFTER_SECONDS = 180

# ⚠️ EXIT CODES ARE PART OF THIS MODULE'S CONTRACT WITH ITS SUPERVISOR.
# `start_alert_relay.bat` restarts the relay on ANY other exit, because a crashed relay is
# a silently dead alert channel. This code means "the problem is configuration and
# restarting cannot fix it" -- without it, the keep-alive loop becomes an infinite respawn
# that looks busy and delivers nothing.
EXIT_CONFIG_REFUSED = 2

SUPPORTED_CHANNELS = ("discord", "sms")
NOT_IMPLEMENTED_CHANNELS = {
    "telegram": (
        "Telegram is NOT_IMPLEMENTED. No bot token exists for this deployment yet. "
        "Refused by name rather than silently ignored: a transport that is advertised "
        "and does nothing is worse than one that is absent, because it reads as coverage."
    )
}


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------
def read_cursor(cursor_path: Path) -> int:
    """Byte offset already delivered. Absent or unreadable means start at 0."""
    try:
        data = json.loads(cursor_path.read_text(encoding="utf-8"))
        return int(data.get("offset", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def write_cursor(cursor_path: Path, offset: int) -> None:
    tmp = cursor_path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"offset": offset}), encoding="utf-8")
    os.replace(tmp, cursor_path)


def read_new_alerts(outbox: Path, cursor_path: Path) -> Tuple[List[Dict[str, Any]], int]:
    """Return (alerts, new_offset) for everything appended since the last read.

    ⚠️ A SHRUNK FILE RESETS THE CURSOR. The outbox is append-only in normal operation, but
    it can be rotated, truncated or deleted between runs -- and a cursor pointing past the
    end of a shorter file would make the relay skip every future alert while reporting
    itself perfectly healthy. That is the silent-failure shape this whole module exists to
    avoid, so it is handled rather than assumed away.
    """
    if not outbox.exists():
        return [], 0

    size = outbox.stat().st_size
    offset = read_cursor(cursor_path)
    if offset > size:
        log.warning(
            "outbox shrank (cursor %d > size %d); restarting from 0. "
            "The file was rotated or truncated.",
            offset,
            size,
        )
        offset = 0

    # ⚠️ BINARY, AND THE OFFSET IS COUNTED IN BYTES CONSUMED -- not `f.tell()` on a text
    # handle being iterated. The first version did exactly that, and its own test caught
    # it: `for line in f` reads ahead in buffered CHUNKS, so `tell()` reports a position
    # PAST the torn final line, and the cursor is then saved beyond a record that was
    # never delivered. The alert is skipped permanently and nothing anywhere says so --
    # the silent-loss failure this whole module exists to prevent, reintroduced in the
    # function meant to prevent it.
    #
    # Only COMPLETE lines (those terminated by a newline) advance the cursor, so a record
    # still being appended is re-read next poll rather than half-parsed and dropped.
    alerts: List[Dict[str, Any]] = []
    consumed = 0
    with open(outbox, "rb") as f:
        f.seek(offset)
        remainder = f.read()

    for raw in remainder.split(b"\n")[:-1]:          # [:-1] drops the unterminated tail
        consumed += len(raw) + 1                     # +1 for the newline itself
        # ⚠️ STRIP A UTF-8 BOM. The guard's writer used `Encoding.UTF8`, which emits
        # `EF BB BF` when it CREATES the file -- so the first line of every new outbox
        # carried one and `json.loads` refused it. Measured live 2026-08-15: the first
        # alert of the first outbox was lost, and the first alert is by construction the
        # one saying something started going wrong.
        #
        # The producer is fixed (UTF8Encoding(false)), and this stays anyway: outboxes
        # written by the old build already exist on disk, and a consumer that only works
        # against a corrected producer would silently drop their first line forever.
        text = raw.strip().lstrip(b"\xef\xbb\xbf")
        if not text:
            continue
        try:
            alerts.append(json.loads(text.decode("utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # A complete but unparseable line is a corrupt record, not a partial one.
            # Skipping it is correct -- re-reading forever would wedge the relay -- but
            # it is logged, because a silent drop here is indistinguishable from calm.
            log.warning("skipping an unparseable outbox line at offset %d", offset + consumed)

    return alerts, offset + consumed


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def format_alert(alert: Dict[str, Any]) -> str:
    """Render one decided alert.

    The guard has already made every judgement -- severity, whether it is a [WOULD], the
    suppression budget. This adds no policy of its own, deliberately: a second opinion
    here would be a second reader of the same state, and every one of those in these repos
    has eventually disagreed with the first.
    """
    title = alert.get("title") or alert.get("eventType") or "(untitled)"
    body = alert.get("body") or ""
    return f"**{title}**\n{body}".strip()


def format_heartbeat(guard_dir: Path, delivered: int, now: Optional[datetime] = None) -> str:
    """The liveness message. Reports the GUARD's freshness as well as the relay's.

    ⚠️ IT MUST BE ABLE TO SAY SOMETHING BAD. A heartbeat that always reads "all good" is a
    green that can never be red -- `nt_health`'s `feedConnected` was `Account.All.Count > 0`
    and was therefore true on every box forever. This one reports the guard as STALE when
    its heartbeat file is old, which is a state it genuinely reaches.
    """
    now = now or datetime.now(timezone.utc)
    hb = guard_dir / HEARTBEAT_NAME
    try:
        stamp = hb.read_text(encoding="utf-8").strip()
        age = (now - datetime.fromtimestamp(hb.stat().st_mtime, tz=timezone.utc)).total_seconds()
        if age > GUARD_STALE_AFTER_SECONDS:
            guard = f"⚠ STALE — no sweep for {int(age)}s (last stamp {stamp}). NT8 or the addon is down."
        else:
            guard = f"alive, last sweep {int(age)}s ago"
    except (OSError, ValueError):
        guard = "⚠ UNKNOWN — heartbeat.txt is missing or unreadable"

    return (
        "**RiskGuard relay heartbeat**\n"
        f"relay: alive, {delivered} alert(s) delivered since start\n"
        f"guard: {guard}\n"
        "_If these stop arriving, the alert channel is dead — that is the point of this message._"
    )


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
def deliver(
    messages: List[str],
    *,
    webhook_url: str,
    sender: Optional[Callable[..., bool]] = None,
) -> int:
    """Send each message. Returns the number that were CONFIRMED delivered.

    ⚠️ IT COUNTS WHAT THE SENDER CONFIRMED, NOT WHAT WAS ATTEMPTED. `P1-105` in the NT8
    repos assigned `positionClosed = true` on the line after an asynchronous call and so
    recorded that control had reached the line. A relay that reported "12 alerts sent"
    while twelve POSTs were 429'd would be the same lie about the same kind of thing.
    """
    if sender is None:
        from scripts.libs_py.discord import send_message as sender  # type: ignore[assignment]

    delivered = 0
    for msg in messages:
        try:
            if sender(webhook_url, msg):
                delivered += 1
            else:
                log.warning("delivery returned False for one alert; it is NOT counted")
        except Exception:  # delivery must never kill the relay
            log.exception("delivery raised for one alert; it is NOT counted")
    return delivered


def resolve_channel(name: str) -> None:
    """Refuse an unimplemented transport BY NAME."""
    if name in NOT_IMPLEMENTED_CHANNELS:
        raise NotImplementedError(NOT_IMPLEMENTED_CHANNELS[name])
    if name not in SUPPORTED_CHANNELS:
        raise ValueError(
            f"unknown transport {name!r}. Supported: {', '.join(SUPPORTED_CHANNELS)}. "
            f"Not implemented: {', '.join(sorted(NOT_IMPLEMENTED_CHANNELS))}."
        )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run(
    *,
    guard_dir: Path,
    webhook_key: str,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    heartbeat_minutes: int = DEFAULT_HEARTBEAT_MINUTES,
    once: bool = False,
    sender: Optional[Callable[..., bool]] = None,
    webhook_url: Optional[str] = None,
) -> int:
    from scripts.libs_py.discord import load_webhook_url

    if webhook_url is None:
        webhook_url = load_webhook_url(webhook_key)
    if not webhook_url:
        # ⚠️ REFUSE, do not start. A relay that runs with no destination delivers nothing
        # and looks exactly like a quiet trading day -- which is the failure this component
        # is built to make impossible.
        #
        # ⚠️ EXIT CODE 2, AND THE CODE IS LOAD-BEARING. The supervisor restarts this process
        # on any other exit, because a crash must not silently end the alert channel. A
        # misconfiguration is the one failure restarting CANNOT fix, so it gets a code the
        # supervisor is told to stop on -- otherwise the "keep it alive" loop becomes an
        # infinite respawn that fills a log and still delivers nothing.
        log.error(
            "no webhook URL for key %r. Refusing to start: a relay with no destination is "
            "silently indistinguishable from a working one.",
            webhook_key,
        )
        raise SystemExit(EXIT_CONFIG_REFUSED)

    outbox = guard_dir / OUTBOX_NAME
    cursor_path = guard_dir / CURSOR_NAME
    delivered_total = 0
    next_heartbeat = datetime.now(timezone.utc)

    log.info("relay started: outbox=%s channel=%s", outbox, webhook_key)

    while True:
        alerts, new_offset = read_new_alerts(outbox, cursor_path)
        if alerts:
            sent = deliver(
                [format_alert(a) for a in alerts],
                webhook_url=webhook_url,
                sender=sender,
            )
            delivered_total += sent
            # ⚠️ THE CURSOR ADVANCES REGARDLESS. A failed POST must not wedge the relay on
            # one poisoned alert forever -- that would convert a single lost message into
            # total silence, which is far worse. The shortfall is logged and shows up in
            # the heartbeat's count.
            if sent != len(alerts):
                log.warning("delivered %d of %d alerts this poll", sent, len(alerts))
            write_cursor(cursor_path, new_offset)

        now = datetime.now(timezone.utc)
        if now >= next_heartbeat:
            deliver(
                [format_heartbeat(guard_dir, delivered_total, now)],
                webhook_url=webhook_url,
                sender=sender,
            )
            next_heartbeat = now + timedelta(minutes=heartbeat_minutes)

        if once:
            return delivered_total
        time.sleep(poll_seconds)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--channel", default="test_channel",
                   help="key in discord_webhooks.json (default: test_channel)")
    p.add_argument("--guard-dir", type=Path, default=DEFAULT_GUARD_DIR)
    p.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    p.add_argument("--heartbeat-minutes", type=int, default=DEFAULT_HEARTBEAT_MINUTES)
    p.add_argument("--once", action="store_true",
                   help="drain the outbox once and exit (used by tests and by hand)")
    p.add_argument("--transport", default="discord",
                   help=f"one of {', '.join(SUPPORTED_CHANNELS)}; "
                        f"{', '.join(sorted(NOT_IMPLEMENTED_CHANNELS))} is refused by name")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # An unimplemented or unknown transport is configuration, not a transient fault, so it
    # exits with the code the supervisor stops on rather than being respawned forever.
    try:
        resolve_channel(args.transport)
    except (NotImplementedError, ValueError) as exc:
        log.error("%s", exc)
        return EXIT_CONFIG_REFUSED

    delivered = run(
        guard_dir=args.guard_dir,
        webhook_key=args.channel,
        poll_seconds=args.poll_seconds,
        heartbeat_minutes=args.heartbeat_minutes,
        once=args.once,
    )
    log.info("delivered %d alert(s)", delivered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
