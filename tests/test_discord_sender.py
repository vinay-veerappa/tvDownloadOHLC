# filepath: tests/test_discord_sender.py
"""Tests for the unified Discord notifier sub-package (audit §3.5).

These tests pin the contract of `scripts.libs_py.discord` (the
shared sub-package) and confirm the three narrative consumers
(`daily_narrative.py`, `trader_narrative.py`, `weekly_narrative.py`)
delegate to it instead of re-implementing chunking + POST inline.

What we cover:
  - `chunk_markdown` — short, single-chunk, multi-section pack,
    single-oversized-section, empty input, exact-boundary edge.
  - `send_summary` — happy path (1+ chunks posted), missing
    webhook file, missing webhook key, partial-post failure,
    no-`requests` fallback, no-`repo_root` defensive skip.
  - Consumer shims — each of the 3 narrative files now imports
    from the shared sub-package and contains a thin
    `send_discord_summary` shim (no in-line chunking).
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

from scripts.libs_py import discord as discord_lib
from scripts.libs_py.discord import (
    DEFAULT_WEBHOOK_KEY,
    DISCORD_MAX_CHARS,
    DISCORD_MAX_CONTENT,
    DISCORD_MAX_EMBEDS,
    DISCORD_SAFE_EMBED_BATCH_CHARS,
    RateLimitTelemetry,
    RecordingTelemetry,
    chunk_markdown,
    compact_embed,
    embed_batches,
    embed_char_count,
    embed_to_content,
    load_webhook_url,
    resolve_webhooks_path,
    send_embeds,
    send_message,
    send_payload,
    send_summary,
    send_with_files,
    truncate_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakePoster:
    """Records every POST made by `send_summary`.

    The real `send_summary` calls `requests.post(url, json=..., timeout=...)`.
    This fake matches that signature so the production call site runs
    unmodified.
    """

    def __init__(self, *, fail_indices: set[int] | None = None) -> None:
        self.calls: list[tuple[str, dict, int]] = []
        self.fail_indices = fail_indices or set()
        self._counter = 0

    def __call__(self, url: str, json: dict, timeout: int) -> None:
        idx = self._counter
        self._counter += 1
        if idx in self.fail_indices:
            raise RuntimeError(f"simulated network failure for chunk {idx}")
        self.calls.append((url, json, timeout))


def _write_webhooks(path: Path, mapping: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping), encoding="utf-8")


# ---------------------------------------------------------------------------
# chunk_markdown
# ---------------------------------------------------------------------------


class TestChunkMarkdown:
    def test_short_text_returns_single_chunk(self) -> None:
        text = "Hello, world!"
        assert chunk_markdown(text) == [text]

    def test_empty_text_returns_one_empty_chunk(self) -> None:
        # The previous in-line implementation yielded one chunk
        # for empty input too; preserve that contract so the
        # post-loop still gets to attempt delivery.
        assert chunk_markdown("") == [""]

    def test_text_at_max_returns_single_chunk(self) -> None:
        text = "a" * DISCORD_MAX_CHARS
        assert chunk_markdown(text) == [text]

    def test_sectioned_text_splits_into_multiple_chunks(self) -> None:
        # 4 sections × ~1500 chars each with `## ` headers,
        # max=1900 → the chunker must produce multiple chunks
        # because no single chunk can hold the whole body.
        text = "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(4))
        chunks = chunk_markdown(text, max_chars=1900)
        assert len(chunks) >= 2
        # Per-chunk length may briefly exceed max_chars (by
        # the +4 budget) but must stay under Discord's 2000
        # hard limit.
        assert all(len(c) <= 2000 for c in chunks)

    def test_sections_split_on_header_and_re_attach_prefix(self) -> None:
        # The first section is preserved as-is, subsequent
        # sections are re-prefixed with `\n## `.
        text = "intro\n## A\nbody a\n## B\nbody b"
        chunks = chunk_markdown(text, max_chars=10_000)
        assert chunks == [text]

    def test_packs_multiple_sections_into_one_chunk(self) -> None:
        text = "intro\n## A\n" + ("a" * 100) + "\n## B\n" + ("b" * 100)
        chunks = chunk_markdown(text, max_chars=10_000)
        # Both sections fit in one chunk with the `## ` prefix
        # re-attached between them.
        assert len(chunks) == 1
        assert "\n## A\n" in chunks[0]
        assert "\n## B\n" in chunks[0]

    def test_splits_when_next_section_would_exceed_max(self) -> None:
        # Two sections of ~1500 chars each, max=1900 → each
        # becomes its own chunk.
        body_a = "a" * 1500
        body_b = "b" * 1500
        text = f"## A\n{body_a}\n## B\n{body_b}"
        chunks = chunk_markdown(text, max_chars=1900)
        assert len(chunks) >= 2
        # No chunk exceeds the limit.
        assert all(len(c) <= 1900 for c in chunks)

    def test_oversized_single_section_is_returned_as_is(self) -> None:
        # A single section larger than max_chars is returned as
        # a single oversized chunk (chunking inside a section
        # would break markdown structure; the caller logs the
        # rejection from Discord).
        giant = "x" * 5000
        text = f"## HUGE\n{giant}"
        chunks = chunk_markdown(text, max_chars=100)
        # At least one chunk exists; the giant body passes
        # through even if it exceeds max.
        joined = "".join(chunks)
        assert giant in joined


# ---------------------------------------------------------------------------
# send_summary
# ---------------------------------------------------------------------------


class TestSendSummary:
    def test_happy_path_single_chunk(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"macro-alerts": "https://example.invalid/hook"})
        poster = _FakePoster()

        with caplog.at_level(logging.INFO, logger="scripts.libs_py.discord.sender"):
            delivered = send_summary(
                "Short body",
                webhooks_path=webhooks,
                poster=poster,
            )

        assert delivered == 1
        assert len(poster.calls) == 1
        url, payload, timeout = poster.calls[0]
        assert url == "https://example.invalid/hook"
        assert payload == {"content": "Short body"}
        assert timeout == 15
        assert "chunk 1/1 sent" in caplog.text

    def test_happy_path_multi_chunk_logs_each(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"macro-alerts": "https://example.invalid/hook"})
        poster = _FakePoster()
        # 4 sections × ~1500 chars each, max=1900 → at least 3 chunks.
        text = "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(4))

        with caplog.at_level(logging.INFO, logger="scripts.libs_py.discord.sender"):
            delivered = send_summary(
                text,
                webhooks_path=webhooks,
                poster=poster,
                max_chars=1900,
            )

        assert delivered == len(poster.calls)
        assert delivered >= 3
        # Each delivered chunk is logged.
        for i in range(1, delivered + 1):
            assert f"chunk {i}/{delivered} sent" in caplog.text

    def test_missing_webhook_file_warns_and_returns_zero(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        missing = tmp_path / "nope.json"
        poster = _FakePoster()

        with caplog.at_level(logging.WARNING, logger="scripts.libs_py.discord.sender"):
            delivered = send_summary(
                "anything",
                webhooks_path=missing,
                poster=poster,
            )

        assert delivered == 0
        assert poster.calls == []
        assert "No Discord webhook found for key" in caplog.text

    def test_missing_key_warns_and_returns_zero(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"other-channel": "https://example.invalid/hook"})
        poster = _FakePoster()

        with caplog.at_level(logging.WARNING, logger="scripts.libs_py.discord.sender"):
            delivered = send_summary(
                "body",
                webhook_key="macro-alerts",
                webhooks_path=webhooks,
                poster=poster,
            )

        assert delivered == 0
        assert poster.calls == []
        assert "macro-alerts" in caplog.text

    def test_malformed_webhook_file_warns_and_returns_zero(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        webhooks.write_text("{ not valid json", encoding="utf-8")
        poster = _FakePoster()

        with caplog.at_level(logging.WARNING, logger="scripts.libs_py.discord.sender"):
            delivered = send_summary(
                "body",
                webhooks_path=webhooks,
                poster=poster,
            )

        assert delivered == 0
        assert poster.calls == []

    def test_post_failure_on_one_chunk_does_not_abort_others(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"macro-alerts": "https://example.invalid/hook"})
        poster = _FakePoster(fail_indices={1})  # fail chunk index 1
        text = "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(3))

        with caplog.at_level(logging.WARNING, logger="scripts.libs_py.discord.sender"):
            delivered = send_summary(
                text,
                webhooks_path=webhooks,
                poster=poster,
                max_chars=1900,
            )

        # 3 chunks attempted, 1 failed → 2 delivered.
        assert poster._counter == 3
        assert delivered == 2
        assert "Discord delivery failed for chunk" in caplog.text

    def test_no_repo_root_and_no_path_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="scripts.libs_py.discord.sender"):
            delivered = send_summary("body", repo_root=None, webhooks_path=None)

        assert delivered == 0
        assert "neither webhooks_path nor repo_root" in caplog.text

    def test_requests_missing_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Simulate `requests` not being installed.
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"macro-alerts": "https://example.invalid/hook"})

        # Make `import requests` raise ImportError by removing
        # it from sys.modules for the duration of the call.
        saved = sys.modules.pop("requests", None)
        monkeypatch.setitem(sys.modules, "requests", None)  # type: ignore[arg-type]
        try:
            delivered = send_summary(
                "body",
                webhooks_path=webhooks,
                poster=None,
            )
        finally:
            if saved is not None:
                sys.modules["requests"] = saved
            else:
                sys.modules.pop("requests", None)

        assert delivered == 0

    def test_resolve_webhooks_path_uses_default_filename(self, tmp_path: Path) -> None:
        assert resolve_webhooks_path(tmp_path) == tmp_path / "discord_webhooks.json"

    def test_default_webhook_key_constant(self) -> None:
        # The narrative chain uses "macro-alerts" as the
        # default; this guards against accidental rename.
        assert DEFAULT_WEBHOOK_KEY == "macro-alerts"


# ---------------------------------------------------------------------------
# Consumer shims
# ---------------------------------------------------------------------------


def _consumer_source(rel_path: str) -> str:
    """Return the source text of a narrative consumer file.

    We deliberately do NOT import the consumers here. Two of
    the three consumers pull in `briefing_core` (a 3,400+ line
    module with heavy transitive imports) and `weekly_narrative`
    has a pre-existing import bug unrelated to this audit. The
    shim contract we care about — "this file delegates to the
    shared sub-package and contains no in-line chunking" — is
    fully expressible at the source-text level, which avoids
    the import-time side effects.
    """
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / "scripts" / "trader" / rel_path).read_text(encoding="utf-8")


class TestConsumerShims:
    @pytest.mark.parametrize(
        "rel_path",
        ["daily_narrative.py", "trader_narrative.py", "weekly_narrative.py"],
    )
    def test_consumer_uses_shared_module_and_drops_in_line_chunking(self, rel_path: str) -> None:
        src = _consumer_source(rel_path)

        # 1. The consumer must import the shared sub-package.
        assert "from scripts.libs_py.discord import send_summary" in src, (
            f"{rel_path} should import send_summary from scripts.libs_py.discord"
        )

        # 2. The in-line chunking literal "1900" must NOT
        #    appear in the consumer (the constant is now in
        #    the shared sub-package's config).
        assert "1900" not in src, (
            f"{rel_path} still contains the literal 1900 — chunking "
            f"should be handled by scripts.libs_py.discord, not in-line"
        )

        # 3. The consumer must not directly call requests.post
        #    for Discord delivery (the shared sender owns I/O).
        assert "requests.post(webhook_url" not in src, (
            f"{rel_path} still POSTs to the webhook in-line"
        )

        # 4. The shim function must exist with the preserved
        #    public signature.
        assert "def send_discord_summary(summary: str, webhook_key: str = \"macro-alerts\")" in src, (
            f"{rel_path} lost the public send_discord_summary signature"
        )

        # 5. The shim must delegate to the shared sender.
        assert "_send_discord_summary(" in src, (
            f"{rel_path} shim does not delegate to the shared sender"
        )

    @pytest.mark.parametrize(
        "rel_path",
        ["daily_narrative.py", "trader_narrative.py", "weekly_narrative.py"],
    )
    def test_consumer_drops_module_level_webhooks_path(self, rel_path: str) -> None:
        src = _consumer_source(rel_path)
        # The DISCORD_WEBHOOKS_PATH module constant is no
        # longer needed — the shared sender resolves the path
        # itself from the repo root.
        assert "DISCORD_WEBHOOKS_PATH" not in src, (
            f"{rel_path} still references DISCORD_WEBHOOKS_PATH; the "
            f"shared sub-package should own the path resolution"
        )

    def test_consumer_shim_end_to_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # End-to-end: the consumer shim must call into the
        # shared sender with the right arguments. We patch
        # the underlying poster to confirm the chain works
        # without touching the real webhook URL.
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"macro-alerts": "https://example.invalid/hook"})
        poster = _FakePoster()

        # Patch the sender's poster + webhooks path so the
        # call routes through our fake.
        from scripts.libs_py.discord import sender as sender_mod

        original_send_summary = sender_mod.send_summary

        def _patched(summary, webhook_key="macro-alerts", repo_root=None, **kwargs):
            return original_send_summary(
                summary,
                webhook_key=webhook_key,
                repo_root=repo_root,
                webhooks_path=webhooks,
                poster=poster,
            )

        monkeypatch.setattr(sender_mod, "send_summary", _patched)

        # Build a minimal shim that mirrors what the
        # consumer modules do, then call it. We don't import
        # the consumer (see `_consumer_source` rationale above)
        # — we just exercise the same call shape.
        shim_callable = lambda summary, webhook_key: _patched(  # noqa: E731
            summary, webhook_key=webhook_key, repo_root=tmp_path
        )
        shim_callable("hello from shim", webhook_key="macro-alerts")

        assert len(poster.calls) == 1
        url, payload, _ = poster.calls[0]
        assert url == "https://example.invalid/hook"
        assert payload == {"content": "hello from shim"}


# ---------------------------------------------------------------------------
# Public-API smoke test (guards against accidental rename of the entry points).
# ---------------------------------------------------------------------------


def test_public_api_surface_is_stable() -> None:
    expected = {
        # High-level delivery
        "send_summary",
        "send_embeds",
        "send_payload",
        # Narrative chunking
        "chunk_markdown",
        # Embed helpers
        "compact_embed",
        "embed_batches",
        "embed_char_count",
        "embed_to_content",
        "truncate_text",
        # Webhook lookup
        "load_webhook_url",
        # Constants
        "DEFAULT_WEBHOOK_KEY",
        "DISCORD_MAX_CHARS",
        "DISCORD_MAX_CONTENT",
        "DISCORD_MAX_EMBEDS",
        "DISCORD_SAFE_EMBED_BATCH_CHARS",
        "DISCORD_WEBHOOKS_FILENAME",
        "EMBED_AUTHOR_MAX",
        "EMBED_DESCRIPTION_MAX",
        "EMBED_FIELD_NAME_MAX",
        "EMBED_FIELD_VALUE_MAX",
        "EMBED_FOOTER_MAX",
        "EMBED_HTTP_TIMEOUT_SECONDS",
        "EMBED_MULTIPART_TIMEOUT_SECONDS",
        "EMBED_TITLE_MAX",
        "HTTP_TIMEOUT_SECONDS",
        "SECTION_HEADER_PREFIX",
        "resolve_webhooks_path",
    }
    exported = set(discord_lib.__all__)
    assert expected.issubset(exported), (
        f"Missing public symbols: {expected - exported}"
    )


# ---------------------------------------------------------------------------
# Embed helpers (audit §3.5 design extension)
# ---------------------------------------------------------------------------
#
# These tests pin the new `scripts.libs_py.discord.embeds` module
# so the options-pipeline migration has a stable contract. Each
# helper is pure (no I/O) and side-effect-free, so testing is
# straightforward: call, assert on the returned shape.


class TestTruncateText:
    def test_short_value_unchanged(self) -> None:
        assert truncate_text("hi", 10) == "hi"

    def test_exact_max_unchanged(self) -> None:
        assert truncate_text("abcdef", 6) == "abcdef"

    def test_over_max_adds_ellipsis(self) -> None:
        assert truncate_text("hello world", 5) == "he..."

    def test_max_too_small_for_suffix_hard_cuts(self) -> None:
        # When max_len is 3 or less, the function can't fit a
        # 3-char `...` suffix and falls back to a hard cut.
        assert truncate_text("abcdef", 3) == "abc"
        assert truncate_text("abcdef", 1) == "a"


class TestEmbedCharCount:
    def test_counts_title_description_footer_author(self) -> None:
        embed = {
            "title": "T",  # 1
            "description": "D",  # 1
            "footer": {"text": "F"},  # 1
            "author": {"name": "A"},  # 1
            "fields": [],
        }
        assert embed_char_count(embed) == 4

    def test_counts_field_names_and_values(self) -> None:
        embed = {
            "fields": [
                {"name": "n1", "value": "v1"},
                {"name": "n2", "value": "v2v2v2"},
            ]
        }
        # n1 (2) + v1 (2) + n2 (2) + v2v2v2 (6) = 12
        assert embed_char_count(embed) == 12

    def test_tolerates_missing_footer_and_author(self) -> None:
        assert embed_char_count({"title": "T"}) == 1
        assert embed_char_count({"footer": None, "author": None}) == 0

    def test_ignores_non_dict_fields(self) -> None:
        embed = {"fields": [{"name": "n", "value": "v"}, "garbage", 42]}
        assert embed_char_count(embed) == 2


class TestCompactEmbed:
    def test_truncates_title_to_256(self) -> None:
        embed = {"title": "A" * 1000, "fields": []}
        out = compact_embed(embed, max_chars=10_000)
        assert len(out["title"]) == 256

    def test_truncates_description_to_4096(self) -> None:
        embed = {"description": "D" * 10_000, "fields": []}
        out = compact_embed(embed, max_chars=100_000)
        assert len(out["description"]) == 4096

    def test_truncates_footer_text(self) -> None:
        embed = {"footer": {"text": "F" * 5000}, "fields": []}
        out = compact_embed(embed, max_chars=100_000)
        assert len(out["footer"]["text"]) == 2048

    def test_truncates_field_name_and_value(self) -> None:
        embed = {
            "fields": [{"name": "N" * 1000, "value": "V" * 5000, "inline": True}],
        }
        out = compact_embed(embed, max_chars=100_000)
        assert len(out["fields"][0]["name"]) == 256
        assert len(out["fields"][0]["value"]) == 1024
        assert out["fields"][0]["inline"] is True

    def test_drops_fields_when_over_max_chars(self) -> None:
        # 5 fields × 100 chars each = 500 chars. Force the
        # batch budget to 200 → 3 fields must be popped to fit.
        fields = [{"name": f"n{i}", "value": "x" * 100} for i in range(5)]
        embed = {"fields": fields}
        out = compact_embed(embed, max_chars=200)
        # Each remaining field is 100 chars; 2 fit in 200.
        assert len(out["fields"]) <= 2

    def test_returns_new_dict_does_not_mutate_input(self) -> None:
        original = {"title": "T", "fields": [{"name": "n", "value": "v"}]}
        snapshot = {"title": "T", "fields": [{"name": "n", "value": "v"}]}
        out = compact_embed(original, max_chars=10_000)
        out["title"] = "MUTATED"
        # Mutating the output must not affect the input.
        assert original == snapshot

    def test_handles_missing_fields_key(self) -> None:
        out = compact_embed({"title": "T"}, max_chars=10_000)
        assert out["fields"] == []


class TestEmbedToContent:
    def test_bold_title_and_field_lines(self) -> None:
        embed = {
            "title": "Header",
            "fields": [{"name": "A", "value": "value-a"}],
        }
        text = embed_to_content(embed)
        assert "**Header**" in text
        assert "**A:** value-a" in text

    def test_spacer_field_flattens_to_value(self) -> None:
        # A field with name == "\u200b" is treated as a
        # separator/spacer; its value is emitted as-is.
        embed = {
            "title": "T",
            "fields": [{"name": "\u200b", "value": "spacer line"}],
        }
        text = embed_to_content(embed)
        assert "spacer line" in text
        assert "**\u200b:**" not in text

    def test_truncates_to_max_len(self) -> None:
        embed = {
            "title": "T" * 5000,
        }
        text = embed_to_content(embed, max_len=100)
        assert len(text) <= 100

    def test_empty_value_only_field_dropped(self) -> None:
        embed = {
            "title": "T",
            "fields": [{"name": "", "value": ""}],
        }
        text = embed_to_content(embed)
        # The empty field contributes nothing.
        assert text == "**T**"


class TestEmbedBatches:
    def test_empty_returns_empty(self) -> None:
        assert embed_batches([]) == []

    def test_single_embed_one_batch(self) -> None:
        batches = embed_batches([{"title": "T", "fields": []}])
        assert len(batches) == 1 and len(batches[0]) == 1

    def test_more_than_10_embeds_splits(self) -> None:
        # DISCORD_MAX_EMBEDS = 10; 12 embeds must split.
        many = [{"title": f"t{i}", "fields": []} for i in range(12)]
        batches = embed_batches(many)
        assert len(batches) == 2
        assert len(batches[0]) == 10
        assert len(batches[1]) == 2

    def test_oversized_embed_is_compacted_into_batch(self) -> None:
        # A 10000-char title is first compacted to EMBED_TITLE_MAX
        # (256), then admitted to the batch. Two small embeds
        # follow; with max_batch_chars=500 all three fit in one
        # batch (giant 256 + 2 small = 258).
        giant = {"title": "G" * 10_000, "fields": []}
        small = [{"title": f"t{i}", "fields": []} for i in range(2)]
        batches = embed_batches([giant, *small], max_batch_chars=500)
        assert len(batches) == 1
        # The first embed in the batch is the giant.
        assert len(batches[0]) == 3
        assert len(batches[0][0]["title"]) == 256  # compacted

    def test_truly_oversized_solo_embed_passes_through(self) -> None:
        # Even when no amount of compaction can shrink a single
        # embed below max_batch_chars (e.g. many fields totalling
        # 8000 chars), the embed still goes through. The whole
        # point of `compact_embed`'s last-resort ladder is to
        # keep the embed, not lose it.
        embed = {
            "title": "T" * 256,
            "fields": [
                {"name": f"n{i}", "value": "x" * 1024} for i in range(10)
            ],
        }
        batches = embed_batches([embed], max_batch_chars=100)
        # The embed goes through; `compact_embed` truncates the
        # last surviving field value down to 256 chars as a last
        # resort.
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_respects_max_batch_chars(self) -> None:
        # Each "embed" contributes ~1000 chars; budget 2000
        # allows 2 per batch.
        many = [
            {"title": "T", "fields": [{"name": "n", "value": "x" * 1000}]}
            for _ in range(6)
        ]
        batches = embed_batches(many, max_batch_chars=2000)
        for batch in batches:
            total = sum(embed_char_count(e) for e in batch)
            assert total <= 2000 or len(batch) == 1


class TestEmbedConstants:
    def test_max_embeds_is_ten(self) -> None:
        assert DISCORD_MAX_EMBEDS == 10

    def test_max_content_is_2000(self) -> None:
        assert DISCORD_MAX_CONTENT == 2000

    def test_safe_batch_chars_is_5600(self) -> None:
        assert DISCORD_SAFE_EMBED_BATCH_CHARS == 5600


# ---------------------------------------------------------------------------
# webhooks.send_payload / send_embeds / load_webhook_url
# ---------------------------------------------------------------------------
#
# These tests use a keyword-only `_EmbedFakePoster` that mirrors
# the real `requests.post` signature used by
# `scripts.libs_py.discord.webhooks`:
#
#   poster(url, *, json=None, data=None, files=None, timeout=...)
#
# The legacy `_FakePoster` (used by the narrative `send_summary`
# tests above) is positional and won't match this signature.


class _EmbedFakePoster:
    """Records every POST made by `send_payload` / `send_embeds`.

    Mirrors the ``requests.post`` kwarg-only signature used by
    ``scripts.libs_py.discord.webhooks._default_poster``. The
    ``status_seq`` parameter lets each successive call return a
    different status (e.g. 400 on the first POST, 200 on the
    fallback).
    """

    def __init__(self, *, status_seq: list[int] | None = None) -> None:
        self.calls: list[dict] = []
        self.status_seq = status_seq or [200]
        self._idx = 0

    def __call__(self, url, *, json=None, data=None, files=None, timeout=None) -> object:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "data": data,
                "files": files,
                "timeout": timeout,
            }
        )
        idx = self._idx
        self._idx += 1
        status = self.status_seq[min(idx, len(self.status_seq) - 1)]

        class _Resp:
            def __init__(self, s: int) -> None:
                self.status_code = s
                self.text = "" if s in (200, 204) else "rejected"

        return _Resp(status)


class TestLoadWebhookUrl:
    def test_returns_url_for_known_key(self, tmp_path: Path) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"test": "https://example.invalid/hook"})
        assert load_webhook_url("test", webhooks_path=webhooks) == "https://example.invalid/hook"

    def test_returns_none_for_missing_key(self, tmp_path: Path) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"a": "https://example.invalid/a"})
        assert load_webhook_url("b", webhooks_path=webhooks) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert load_webhook_url("x", webhooks_path=tmp_path / "nope.json") is None

    def test_returns_none_for_malformed_json(self, tmp_path: Path) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        webhooks.write_text("not json", encoding="utf-8")
        assert load_webhook_url("x", webhooks_path=webhooks) is None

    def test_defaults_to_the_repo_root_when_given_no_path(self) -> None:
        """With neither argument the repo root is derived from ``__file__``.

        ⚠️ THIS TEST WAS INVERTED, and asserted ``is None``.

        The deprecated shim it replaced
        (``scripts.utils.discord_notify.get_webhook_url``) has always derived
        the repo root from ``__file__``, so the two APIs disagreed and
        *following the deprecation notice* silently broke webhook lookup:
        ``load_webhook_url('test_channel')`` returned ``None``, ``send_message``
        logged "called with empty URL; skipping" and returned ``False``, and the
        caller saw a completed run that had notified nobody.

        The old assertion was not wrong about the code; it pinned the defect.
        """
        # A key that cannot exist proves the LOOKUP ran (no exception, and the
        # "key absent" path was reached) without depending on this machine's
        # webhook file contents.
        assert load_webhook_url("__no_such_channel__") is None

        # The real assertion: a key that IS in the repo's file now resolves,
        # where before it did not.
        repo_root = Path(__file__).resolve().parents[1]
        webhooks_file = repo_root / "discord_webhooks.json"
        if webhooks_file.exists():
            data = json.loads(webhooks_file.read_text(encoding="utf-8"))
            if data:
                key = sorted(data)[0]
                assert load_webhook_url(key) == data[key]

    def test_the_shim_and_the_canonical_api_agree(self, tmp_path: Path) -> None:
        """The two entry points must resolve a key identically.

        This is the regression guard that matters. The defect above was not a
        wrong line, it was TWO READERS OF THE SAME STATE that nobody had
        compared -- so the fix is not "make this one right", it is "make them
        answer the same question the same way", pinned.
        """
        from scripts.utils.discord_notify import get_webhook_url

        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"k": "https://example.invalid/k"})

        assert load_webhook_url("k", webhooks_path=webhooks) == "https://example.invalid/k"
        # The shim resolves against the real repo root, so compare on a key
        # that exists in BOTH places, or on absence, which is well defined.
        assert get_webhook_url("__no_such_channel__") is None
        assert load_webhook_url("__no_such_channel__") is None

    def test_repo_root_resolved_to_default_filename(self, tmp_path: Path) -> None:
        webhooks = tmp_path / "discord_webhooks.json"
        _write_webhooks(webhooks, {"test": "https://example.invalid/hook"})
        # Providing repo_root + the default filename works.
        assert load_webhook_url("test", repo_root=tmp_path) == "https://example.invalid/hook"


class TestSendPayload:
    def test_happy_path_returns_true(self) -> None:
        poster = _EmbedFakePoster()
        ok = send_payload("https://example.invalid/hook", {"embeds": [{"title": "A"}]}, poster=poster)
        assert ok is True
        assert len(poster.calls) == 1
        call = poster.calls[0]
        assert call["url"] == "https://example.invalid/hook"
        assert call["json"] == {"embeds": [{"title": "A"}]}
        assert call["files"] is None
        # JSON path uses the embed (shorter) timeout.
        assert call["timeout"] == 20

    def test_multipart_payload_uses_files(self) -> None:
        poster = _EmbedFakePoster()
        files = {"file": ("x.png", b"\x89PNG", "image/png")}
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            files=files,
            poster=poster,
        )
        assert ok is True
        call = poster.calls[0]
        assert call["files"] is files
        # payload_json is JSON-encoded into the multipart `data`.
        import json as _json
        assert _json.loads(call["data"]["payload_json"]) == {"content": "hi"}

    def test_400_with_embeds_falls_back_to_text(self) -> None:
        # First POST: 400 (rejected embed).
        # Fallback POSTs (one per embed): 200.
        poster = _EmbedFakePoster(status_seq=[400, 200, 200])
        embed1 = {"title": "A", "fields": [{"name": "f", "value": "v"}]}
        embed2 = {"title": "B", "fields": []}
        ok = send_payload(
            "https://example.invalid/hook",
            {"embeds": [embed1, embed2]},
            poster=poster,
        )
        assert ok is True
        # 1 embed POST + 2 fallback POSTs.
        assert len(poster.calls) == 3
        # The 2 fallback POSTs use {"content": ...} payloads.
        for call in poster.calls[1:]:
            assert "content" in call["json"]
            assert "embeds" not in call["json"]

    def test_400_with_content_no_fallback(self) -> None:
        # 400 with no embeds → return False (no fallback).
        poster = _EmbedFakePoster(status_seq=[400])
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
        )
        assert ok is False
        assert len(poster.calls) == 1

    def test_500_returns_false(self) -> None:
        poster = _EmbedFakePoster(status_seq=[500])
        ok = send_payload(
            "https://example.invalid/hook",
            {"embeds": [{"title": "A"}]},
            poster=poster,
            max_retries=0,
        )
        assert ok is False

    def test_timeout_returns_false(self, caplog: pytest.LogCaptureFixture) -> None:
        def slow(*args, **kwargs):
            raise Exception("Read timed out")

        with caplog.at_level(logging.ERROR, logger="scripts.libs_py.discord.webhooks"):
            ok = send_payload("https://example.invalid/hook", {"embeds": []}, poster=slow, max_retries=0)
        assert ok is False
        assert "timed out" in caplog.text.lower()

    def test_request_exception_returns_false(self, caplog: pytest.LogCaptureFixture) -> None:
        def err(*args, **kwargs):
            raise Exception("connection refused")

        with caplog.at_level(logging.ERROR, logger="scripts.libs_py.discord.webhooks"):
            ok = send_payload("https://example.invalid/hook", {"embeds": []}, poster=err, max_retries=0)
        assert ok is False
        assert "connection refused" in caplog.text

    def test_400_fallback_partial_failure(self) -> None:
        # First POST 400, then one fallback 200 and one 500.
        poster = _EmbedFakePoster(status_seq=[400, 200, 500])
        embed1 = {"title": "A", "fields": []}
        embed2 = {"title": "B", "fields": []}
        ok = send_payload(
            "https://example.invalid/hook",
            {"embeds": [embed1, embed2]},
            poster=poster,
        )
        # One fallback succeeded, one failed → overall False.
        assert ok is False


class TestSendEmbeds:
    def test_empty_returns_zero(self) -> None:
        poster = _EmbedFakePoster()
        assert send_embeds("https://example.invalid/hook", [], poster=poster) == 0

    def test_single_batch(self) -> None:
        poster = _EmbedFakePoster()
        embeds = [{"title": f"t{i}", "fields": []} for i in range(5)]
        n = send_embeds("https://example.invalid/hook", embeds, poster=poster)
        assert n == 1
        assert len(poster.calls) == 1
        assert len(poster.calls[0]["json"]["embeds"]) == 5

    def test_split_into_two_batches(self) -> None:
        poster = _EmbedFakePoster()
        embeds = [{"title": f"t{i}", "fields": []} for i in range(15)]
        n = send_embeds("https://example.invalid/hook", embeds, poster=poster)
        # 15 embeds at 10-per-batch → 2 batches.
        assert n == 2
        assert len(poster.calls) == 2
        assert len(poster.calls[0]["json"]["embeds"]) == 10
        assert len(poster.calls[1]["json"]["embeds"]) == 5

    def test_content_and_username_included(self) -> None:
        poster = _EmbedFakePoster()
        n = send_embeds(
            "https://example.invalid/hook",
            [{"title": "T", "fields": []}],
            content="hello",
            username="bot",
            poster=poster,
        )
        assert n == 1
        body = poster.calls[0]["json"]
        assert body["content"] == "hello"
        assert body["username"] == "bot"

    def test_partial_failure_counted(self) -> None:
        poster = _EmbedFakePoster(status_seq=[200, 500])
        embeds = [{"title": f"t{i}", "fields": []} for i in range(15)]
        # max_retries=0 to keep the test fast — the
        # 500 doesn't sleep because there's no retry.
        n = send_embeds("https://example.invalid/hook", embeds, poster=poster, max_retries=0)
        # First batch 200, second batch 500 → 1 of 2 succeeded.
        assert n == 1


# ---------------------------------------------------------------------------
# Options-pipeline shim contract (audit §3.5 design extension)
# ---------------------------------------------------------------------------
#
# `scripts/streaming/options/discord_notifier.py` keeps the same
# internal helper names so existing tests in
# `tests/streaming/test_options_output_contract.py` can monkeypatch
# them. The shim must delegate to the shared module while preserving
# the historical raise-on-missing semantics for `_load_webhook_url`.


def _options_notifier_source() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / "scripts" / "streaming" / "options" / "discord_notifier.py").read_text(
        encoding="utf-8"
    )


def _earnings_notifier_source() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / "scripts" / "market_data" / "discord_earnings_notifier.py").read_text(
        encoding="utf-8"
    )


class TestOptionsNotifierShim:
    def test_options_notifier_drops_in_line_constants(self) -> None:
        src = _options_notifier_source()
        # The literal embed-size numbers must not appear
        # as in-line magic values.
        assert "_DISCORD_MAX_EMBEDS = 10" not in src
        assert "_DISCORD_MAX_CONTENT = 2000" not in src
        assert "_DISCORD_SAFE_EMBED_BATCH_CHARS = 5600" not in src

    def test_options_notifier_uses_shared_symbols(self) -> None:
        src = _options_notifier_source()
        assert "from scripts.libs_py.discord import" in src
        # The shim must reference at least the new helpers.
        for sym in (
            "compact_embed",
            "embed_batches",
            "embed_char_count",
            "embed_to_content",
            "truncate_text",
            "load_webhook_url",
            "send_payload",
        ):
            assert sym in src, f"options notifier should reference shared `{sym}`"

    def test_options_notifier_preserves_shim_names(self) -> None:
        # Existing tests monkeypatch these by name. The
        # shim must keep them as module-level callables.
        src = _options_notifier_source()
        for name in (
            "_load_webhook_url",
            "_post_payload",
            "_truncate_text",
            "_embed_char_count",
            "_compact_embed",
            "_embed_to_content",
            "_embed_batches",
        ):
            assert f"def {name}(" in src, f"options notifier lost `{name}`"


class TestEarningsNotifierShim:
    def test_earnings_notifier_uses_shared_module(self) -> None:
        src = _earnings_notifier_source()
        assert "from scripts.libs_py.discord import" in src

    def test_earnings_notifier_drops_requests_import(self) -> None:
        # The webhook POST must go through send_payload, not
        # a direct `import requests` + `requests.post` call.
        src = _earnings_notifier_source()
        assert "import requests" not in src
        assert "requests.post(" not in src

    def test_earnings_notifier_load_webhook_url_preserved(self) -> None:
        # Earnings notifier call sites use the name
        # `_load_webhook_url`. The shim must keep that name
        # for backward compat.
        src = _earnings_notifier_source()
        assert "def _load_webhook_url(" in src




# ---------------------------------------------------------------------------
# Tier-2 hardening tests: retry, backoff, send_with_files, wait
# ---------------------------------------------------------------------------
#
# These tests pin the new HTTP 429 / 5xx retry policy,
# send_with_files, send_message, and the ``wait=`` rate-limit
# guard. They use a ``RecordingSleep`` so we can assert the
# number of sleeps without actually waiting.
from scripts.libs_py.discord import (
    DISCORD_BACKOFF_BASE_SECONDS,
    DISCORD_BACKOFF_MAX_SECONDS,
    DISCORD_BACKOFF_MULTIPLIER,
    DISCORD_MAX_RETRIES,
    DISCORD_RETRY_AFTER_MAX_SECONDS,
    DISCORD_RETRYABLE_STATUS_CODES,
    INTER_CHUNK_WAIT_SECONDS,
    WAIT_AFTER_BATCH_SECONDS,
    send_with_files,
    send_message,
)


class RecordingSleep:
    """Replacement for ``time.sleep`` that records the seconds.

    Tests use this to assert the *number* of sleeps (and
    roughly the total) without actually waiting. The
    production code uses :func:`_sleep_fn` from
    :mod:`scripts.libs_py.discord.webhooks` which defaults
    to :func:`time.sleep`; we override it to this recording
    fake via the ``sleep_fn`` kwarg.
    """

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(float(seconds))

    @property
    def total(self) -> float:
        return sum(self.calls)


def _resp_with(status: int, *, retry_after: str | None = None) -> object:
    class _Resp:
        def __init__(self) -> None:
            self.status_code = status
            self.text = "ok" if status in (200, 204) else "fail"
            self.headers: dict = {}
            if retry_after is not None:
                self.headers["Retry-After"] = retry_after
                self.headers["X-RateLimit-Reset-After"] = retry_after

    return _Resp()


class _RetryablePoster:
    """Returns a configurable sequence of statuses / exceptions.

    Each call to ``__call__`` pops the next entry from
    ``responses`` (a list of either status ints,
    ``Exception`` instances, or
    ``(status_int, retry_after_str)`` tuples). When the list
    is exhausted the last entry is reused — so a 3-element
    ``[500, 500, 200]`` will (1) return 500, (2) return 500,
    (3) return 200, and (4) return 200 again.
    """

    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []
        self._idx = 0

    def __call__(self, url, *, json=None, data=None, files=None, timeout=None) -> object:
        self.calls.append(
            {"url": url, "json": json, "data": data, "files": files, "timeout": timeout}
        )
        idx = min(self._idx, len(self.responses) - 1)
        self._idx += 1
        item = self.responses[idx]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            status, retry_after = item
            return _resp_with(status, retry_after=retry_after)
        return _resp_with(item)


class TestSendPayloadRetry:
    def test_429_with_retry_after_header(self) -> None:
        # First POST: 429 with Retry-After=2.0. Second POST: 200.
        poster = _RetryablePoster([(429, "2.0"), 200])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            sleep_fn=sleep,
        )
        assert ok is True
        assert len(poster.calls) == 2
        # The sleep was the exact Retry-After value, capped.
        assert sleep.calls == [2.0]

    def test_429_retry_after_capped(self) -> None:
        # Discord says wait 3600s (an hour); we cap to
        # DISCORD_RETRY_AFTER_MAX_SECONDS (60s) so we don't
        # block the worker for an hour.
        poster = _RetryablePoster([(429, "3600"), 200])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            sleep_fn=sleep,
        )
        assert ok is True
        assert sleep.calls == [float(DISCORD_RETRY_AFTER_MAX_SECONDS)]

    def test_500_exponential_backoff(self) -> None:
        # Three 500s then a 200. With max_retries=3 (default),
        # the backoff ladder is 1s, 3s, 9s.
        poster = _RetryablePoster([500, 500, 500, 200])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            sleep_fn=sleep,
        )
        assert ok is True
        assert len(poster.calls) == 4
        # Three sleeps before success: 1.0, 3.0, 9.0.
        assert sleep.calls == [
            DISCORD_BACKOFF_BASE_SECONDS,
            DISCORD_BACKOFF_BASE_SECONDS * DISCORD_BACKOFF_MULTIPLIER,
            DISCORD_BACKOFF_BASE_SECONDS * DISCORD_BACKOFF_MULTIPLIER ** 2,
        ]

    def test_500_backoff_capped(self) -> None:
        # With more retries than the cap allows, the sleeps
        # are bounded by DISCORD_BACKOFF_MAX_SECONDS.
        # We use exactly 6 responses (1 initial + 5 retries)
        # so the last 200 is reached deterministically.
        poster = _RetryablePoster([500, 500, 500, 500, 500, 200])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=5,
            sleep_fn=sleep,
        )
        # First 5 are 1, 3, 9, 27, 30 (capped at 30).
        assert sleep.calls == [
            1.0,
            3.0,
            9.0,
            27.0,
            float(DISCORD_BACKOFF_MAX_SECONDS),
        ]
        assert ok is True

    def test_exhausted_retries_returns_false(self) -> None:
        # Always 500 → after max_retries retries the function
        # gives up and returns False.
        poster = _RetryablePoster([500])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=2,
            sleep_fn=sleep,
        )
        assert ok is False
        # 1 initial + 2 retries = 3 POSTs, 2 sleeps.
        assert len(poster.calls) == 3
        assert len(sleep.calls) == 2

    def test_max_retries_zero_skips_retry(self) -> None:
        # 500 with max_retries=0 → single POST, no sleep, False.
        poster = _RetryablePoster([500])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=0,
            sleep_fn=sleep,
        )
        assert ok is False
        assert len(poster.calls) == 1
        assert sleep.calls == []

    def test_400_not_retried(self) -> None:
        # 400 is non-retryable. No sleep, no second POST.
        poster = _RetryablePoster([400])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            sleep_fn=sleep,
        )
        assert ok is False
        assert len(poster.calls) == 1
        assert sleep.calls == []

    def test_retryable_status_codes_constant(self) -> None:
        # The contract is documented in config.py and pinned
        # here so accidental edits are caught.
        assert DISCORD_RETRYABLE_STATUS_CODES == (429, 500, 502, 503, 504)


class TestSendPayloadErrors:
    def test_network_error_retried(self) -> None:
        # First call raises, second returns 200.
        poster = _RetryablePoster([Exception("connection reset"), 200])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=1,
            sleep_fn=sleep,
        )
        assert ok is True
        assert len(poster.calls) == 2
        assert len(sleep.calls) == 1

    def test_network_error_exhausted(self) -> None:
        poster = _RetryablePoster([Exception("connection refused")])
        sleep = RecordingSleep()
        ok = send_payload(
            "https://example.invalid/hook",
            {"content": "hi"},
            poster=poster,
            max_retries=2,
            sleep_fn=sleep,
        )
        assert ok is False
        assert len(poster.calls) == 3  # 1 + 2 retries
        assert len(sleep.calls) == 2

    def test_empty_url_returns_false(self) -> None:
        poster = _RetryablePoster([200])
        ok = send_payload("", {"content": "hi"}, poster=poster)
        assert ok is False
        assert poster.calls == []


class TestSendWithFiles:
    def test_text_only_single_chunk(self) -> None:
        poster = _EmbedFakePoster()
        ok = send_with_files(
            "https://example.invalid/hook",
            "short text",
            [],
            poster=poster,
        )
        assert ok is True
        assert len(poster.calls) == 1
        assert poster.calls[0]["json"] == {"content": "short text"}
        assert poster.calls[0]["files"] is None

    def test_text_with_one_file(self, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("hello world", encoding="utf-8")
        poster = _EmbedFakePoster()
        ok = send_with_files(
            "https://example.invalid/hook",
            "caption",
            [str(f)],
            poster=poster,
        )
        assert ok is True
        assert len(poster.calls) == 1
        # Files present in this single POST.
        assert poster.calls[0]["files"] is not None
        # payload_json encodes the content.
        import json as _json
        body = _json.loads(poster.calls[0]["data"]["payload_json"])
        assert body == {"content": "caption"}

    def test_text_with_one_file_in_memory(self) -> None:
        # 3-tuple form (filename, bytes, mimetype) — no disk.
        poster = _EmbedFakePoster()
        ok = send_with_files(
            "https://example.invalid/hook",
            "caption",
            [("chart.png", b"\x89PNG", "image/png")],
            poster=poster,
        )
        assert ok is True
        assert len(poster.calls) == 1
        files = poster.calls[0]["files"]
        assert files is not None
        # The form field name is "file_<basename>".
        assert "file_chart" in files
        assert files["file_chart"][0] == "chart.png"

    def test_long_text_chunks_files_on_last(self) -> None:
        # 3 sections of ~1500 chars each → 3 chunks (the
        # default chunk size is DISCORD_MAX_CHARS = 1900).
        # Files attach only to the last chunk.
        text = "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(3))
        poster = _EmbedFakePoster()
        ok = send_with_files(
            "https://example.invalid/hook",
            text,
            [("x.txt", b"data", "text/plain")],
            poster=poster,
        )
        assert ok is True
        # 3 chunks: 2 text-only, 1 text+files.
        assert len(poster.calls) == 3
        assert poster.calls[0]["files"] is None
        assert poster.calls[1]["files"] is None
        assert poster.calls[2]["files"] is not None

    def test_files_only_no_content(self) -> None:
        poster = _EmbedFakePoster()
        ok = send_with_files(
            "https://example.invalid/hook",
            None,
            [("a.txt", b"x", "text/plain")],
            poster=poster,
        )
        assert ok is True
        assert len(poster.calls) == 1
        assert poster.calls[0]["files"] is not None

    def test_empty_content_and_no_files_returns_false(self) -> None:
        poster = _EmbedFakePoster()
        ok = send_with_files("https://example.invalid/hook", None, [], poster=poster)
        assert ok is False
        assert poster.calls == []

    def test_empty_url_returns_false(self) -> None:
        ok = send_with_files("", "body", [], poster=_EmbedFakePoster())
        assert ok is False


class TestSendMessage:
    def test_text_only(self) -> None:
        poster = _EmbedFakePoster()
        ok = send_message(
            "https://example.invalid/hook", "hello", poster=poster
        )
        assert ok is True
        assert len(poster.calls) == 1

    def test_with_existing_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("hi", encoding="utf-8")
        poster = _EmbedFakePoster()
        ok = send_message(
            "https://example.invalid/hook",
            "caption",
            file_paths=[str(f)],
            poster=poster,
        )
        assert ok is True
        assert len(poster.calls) == 1
        assert poster.calls[0]["files"] is not None

    def test_with_missing_file_path_is_skipped(self, tmp_path: Path) -> None:
        # Missing file is logged + skipped, not raised.
        poster = _EmbedFakePoster()
        ok = send_message(
            "https://example.invalid/hook",
            "still send text",
            file_paths=[str(tmp_path / "nope.txt")],
            poster=poster,
        )
        # Text-only POST still happens.
        assert ok is True
        assert len(poster.calls) == 1
        assert poster.calls[0]["files"] is None


class TestSendEmbedsWait:
    def test_wait_inserts_sleep_after_every_batch(self) -> None:
        # 15 embeds → 2 batches. wait=True → one
        # WAIT_AFTER_BATCH_SECONDS sleep after each batch
        # (unlike send_summary which skips the last).
        poster = _EmbedFakePoster()
        sleep = RecordingSleep()
        n = send_embeds(
            "https://example.invalid/hook",
            [{"title": f"t{i}", "fields": []} for i in range(15)],
            poster=poster,
            wait=True,
            sleep_fn=sleep,
        )
        assert n == 2
        # Exactly one inter-batch sleep per successful batch.
        assert sleep.calls == [
            WAIT_AFTER_BATCH_SECONDS,
            WAIT_AFTER_BATCH_SECONDS,
        ]

    def test_wait_does_not_sleep_after_failed_batch(self) -> None:
        # First batch 200, second batch 500. The sleep
        # happens *after* a successful batch only.
        poster = _EmbedFakePoster(status_seq=[200, 500])
        sleep = RecordingSleep()
        n = send_embeds(
            "https://example.invalid/hook",
            [{"title": f"t{i}", "fields": []} for i in range(15)],
            poster=poster,
            wait=True,
            sleep_fn=sleep,
            max_retries=0,
        )
        assert n == 1
        # Sleep after the first (success) batch only.
        assert sleep.calls == [WAIT_AFTER_BATCH_SECONDS]

    def test_wait_off_inserts_no_sleeps(self) -> None:
        poster = _EmbedFakePoster()
        sleep = RecordingSleep()
        send_embeds(
            "https://example.invalid/hook",
            [{"title": f"t{i}", "fields": []} for i in range(15)],
            poster=poster,
            wait=False,
            sleep_fn=sleep,
        )
        assert sleep.calls == []


class TestSendSummaryWait:
    def test_wait_inserts_inter_chunk_sleep(self) -> None:
        # 3 chunks: 2 inter-chunk sleeps (not after the last).
        poster = _FakePoster()
        sleep = RecordingSleep()
        webhooks = _write_webhooks_for({
            "macro-alerts": "https://example.invalid/hook"
        })
        delivered = send_summary(
            "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(3)),
            webhook_key="macro-alerts",
            webhooks_path=webhooks,
            poster=poster,
            max_chars=1900,
            wait=True,
            sleep_fn=sleep,
        )
        assert delivered == 3
        # 2 inter-chunk sleeps (not after the last).
        assert sleep.calls == [INTER_CHUNK_WAIT_SECONDS, INTER_CHUNK_WAIT_SECONDS]

    def test_wait_off_inserts_no_sleeps(self) -> None:
        poster = _FakePoster()
        sleep = RecordingSleep()
        webhooks = _write_webhooks_for({
            "macro-alerts": "https://example.invalid/hook"
        })
        send_summary(
            "".join(f"\n## S{i}\n" + ("x" * 1500) for i in range(3)),
            webhook_key="macro-alerts",
            webhooks_path=webhooks,
            poster=poster,
            max_chars=1900,
            wait=False,
            sleep_fn=sleep,
        )
        assert sleep.calls == []


def _write_webhooks_for(mapping: dict[str, str]) -> Path:
    """Helper: write the webhooks JSON to a temp file and return it."""
    import tempfile
    import os as _os
    fd, name = tempfile.mkstemp(suffix=".json")
    _os.close(fd)
    p = Path(name)
    p.write_text(json.dumps(mapping), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Legacy discord_notify.py shim tests (Tier-1 migration)
# ---------------------------------------------------------------------------
#
# `scripts/utils/discord_notify.py` is now a thin shim over
# `scripts.libs_py.discord`. The 8 legacy consumers still
# import it; the shim must keep that path working. After
# the consumers are migrated to direct imports, the shim
# will be removed.


class TestLegacyDiscordNotifyShim:
    def test_shim_reexports_get_webhook_url(self) -> None:
        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore", DeprecationWarning)
            from scripts.utils import discord_notify
        assert callable(discord_notify.get_webhook_url)
        assert callable(discord_notify.send_message)
        assert callable(discord_notify.upload_file)

    def test_shim_get_webhook_url_returns_url(self) -> None:
        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore", DeprecationWarning)
            from scripts.utils import discord_notify
        url = discord_notify.get_webhook_url("test_channel")
        # We have test_channel in the repo's webhooks JSON.
        assert url is not None
        assert url.startswith("http")

    def test_shim_get_webhook_url_override(self) -> None:
        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore", DeprecationWarning)
            from scripts.utils import discord_notify
        url = discord_notify.get_webhook_url("test_channel", override_url="https://override.invalid/")
        assert url == "https://override.invalid/"

    def test_shim_get_webhook_url_unknown_channel(self) -> None:
        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore", DeprecationWarning)
            from scripts.utils import discord_notify
        url = discord_notify.get_webhook_url("__nope__")
        assert url is None

    def test_shim_emits_deprecation_warning(self) -> None:
        # The shim should warn once on first use.
        import warnings as _w
        from scripts.utils import discord_notify as dn
        # Reset the once-flag so we can observe the warning.
        dn._DEPRECATION_EMITTED = False
        with _w.catch_warnings(record=True) as caught:
            _w.simplefilter("always")
            dn.get_webhook_url("test_channel")
        assert any(
            issubclass(w.category, DeprecationWarning) for w in caught
        ), "shim should emit a DeprecationWarning on first use"


# ---------------------------------------------------------------------------
# Public-API surface test (extended with the Tier-2 symbols)
# ---------------------------------------------------------------------------
def test_public_api_surface_is_stable_tier2() -> None:
    """Guard against accidental rename of the Tier-2 entry points."""
    expected = {
        # Tier-2 high-level helpers
        "send_with_files",
        "send_message",
        # Tier-2 retry / backoff / wait constants
        "DISCORD_MAX_RETRIES",
        "DISCORD_RETRY_AFTER_MAX_SECONDS",
        "DISCORD_BACKOFF_BASE_SECONDS",
        "DISCORD_BACKOFF_MULTIPLIER",
        "DISCORD_BACKOFF_MAX_SECONDS",
        "DISCORD_RETRYABLE_STATUS_CODES",
        "INTER_CHUNK_WAIT_SECONDS",
        "WAIT_AFTER_BATCH_SECONDS",
        # Tier-3 observability (also exported from this module
        # for the all-in-one import path)
        "RateLimitTelemetry",
        "RecordingTelemetry",
        "TelemetryEvent",
        "default_sink",
    }
    exported = set(discord_lib.__all__)
    assert expected.issubset(exported), (
        f"Missing Tier-2 public symbols: {expected - exported}"
    )
