# filepath: scripts/libs_py/discord/chunking.py
"""Pure chunking for Discord message bodies.

This module is intentionally side-effect-free: no I/O, no logging,
no module-import of `requests` or similar. The split strategy mirrors
the previous in-line implementation that was duplicated across three
narrative files (audit §3.5):

  1. If `text` is at or below `max_chars`, return `[text]`.
  2. Otherwise, split on `\n## ` (markdown section header) and pack
     sections greedily into chunks, each held under `max_chars`.
  3. The first section of the original text is kept intact (no
     leading header is added); subsequent sections get their
     `## ` prefix re-attached.

The function is deterministic and unit-testable with no fixtures.
"""
from __future__ import annotations

from .config import SECTION_HEADER_PREFIX


def chunk_markdown(
    text: str,
    max_chars: int = 1900,
    section_header: str = SECTION_HEADER_PREFIX,
) -> list[str]:
    """Split `text` into chunks no longer than `max_chars`.

    Args:
        text: The full markdown body to split.
        max_chars: Hard upper bound on each chunk's length.
        section_header: The literal section-header marker used
            for splitting. Defaults to `"\n## "`.

    Returns:
        A list of chunks. If `text` fits in one chunk, the result
        is `[text]` (no rewriting). If `text` is empty, the result
        is `[""]` (preserves the previous behaviour where the
        caller could rely on at least one chunk being yielded).

    Edge cases:
        - A single section larger than `max_chars` is returned as a
          single oversized chunk (we don't break in the middle of a
          section — Discord will reject it, but that's a content
          problem, not a chunker problem, and is logged by the
          caller).
        - Empty input returns `[""]` (one empty chunk) so the
          post-loop in the caller still gets to attempt one
          delivery; the sender catches the empty case.
    """
    if not text:
        return [""]

    if len(text) <= max_chars:
        return [text]

    # Split on the literal section-header marker. The first element
    # is whatever precedes the first `\n## `; subsequent elements
    # each start with the body of their section (no leading `## `).
    parts = text.split(section_header)
    chunks: list[str] = []
    current = ""

    for part in parts:
        # The first part (index 0) is the pre-header content;
        # everything after is a section body. We always re-attach
        # the header when concatenating so the rendered chunk
        # keeps its markdown structure.
        candidate_body = part
        candidate_with_sep = (
            current + section_header + part if current else part
        )

        # +4 is a defensive budget for the `\n## ` glue (3 chars)
        # plus a trailing newline (1 char). Same value the
        # duplicated code used.
        if len(current) + len(candidate_body) + 4 > max_chars:
            if current:
                chunks.append(current)
            # Re-attach the leading `## ` so the next section
            # renders as a header. The first part is special-cased
            # because the original text didn't have a header
            # before it.
            current = part if not current else section_header + part
            # Track the candidate length for the case where the
            # very first section is itself > max_chars — we want
            # to keep it as its own chunk rather than silently
            # extending `current`.
            if len(current) > max_chars:
                chunks.append(current)
                current = ""
        else:
            current = candidate_with_sep

    if current:
        chunks.append(current)

    return chunks
