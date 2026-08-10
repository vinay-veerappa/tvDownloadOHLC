"""
regions.py
==========
Locate an editable source region by declaration, not by line number.

Line numbers drift the moment an earlier ticket lands; anchoring on the
declaration means a ticket file written today still resolves after ten
unrelated commits. That idea is carried over from the original loop unchanged.

The extent is still found by brace matching over a comment/string stripper,
because that is demonstrably correct here: across all 18 regions in
tickets_p0.json it agrees byte-for-byte with a real tree-sitter parse. A
parser dependency would have bought zero behaviour change.

What it cannot handle is C# verbatim strings (`@"C:\\path"` -- the backslash
reads as an escape and eats the closing quote) and /* */ block comments.
Neither appears anywhere in the addons today (checked: zero occurrences in
RiskGuardAddOn.cs and TradeCopierEngine.cs), but if one is ever added, a
miscounted brace silently moves the region boundary and the loop splices a
replacement over the wrong span -- corruption with no error.

So `guard_unsupported_syntax` refuses to resolve a file containing either
construct. The failure becomes a loud, actionable error instead of a silent
bad edit, which is the property that actually matters. Whoever adds the first
verbatim string gets told to upgrade the locator; until then we carry no
dependency for it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SUPPORTED_SUFFIXES = (".cs",)

# Constructs the stripper below cannot parse. See the module docstring: these
# are refused rather than mis-parsed.
_UNSUPPORTED = (
    ('@"', "C# verbatim string"),
    ("/*", "block comment"),
)


class RegionError(LookupError):
    """Anchor missing, ambiguous, or in a file this locator cannot parse."""


def guard_unsupported_syntax(path: Path, src: str) -> None:
    """Refuse a file containing syntax the brace matcher would silently misread.

    Cheap insurance: the cost of being wrong here is a replacement spliced over
    the wrong line span, which no later gate reliably catches because the
    result usually still compiles.
    """
    for token, label in _UNSUPPORTED:
        if token in src:
            line = src[: src.index(token)].count("\n") + 1
            raise RegionError(
                f"{path.name}:{line} contains a {label} ({token!r}), which this "
                f"locator cannot parse safely. Upgrade regions.py to a real "
                f"parser (tree-sitter) before editing this file."
            )


def language_for(path: Path) -> str:
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise RegionError(f"no configured language for suffix {path.suffix!r} ({path})")
    return "c_sharp"


def strip_code(line: str) -> str:
    """Blank out // comments and string/char literal bodies for brace counting.

    Interpolated strings ($"...{x}...") are handled correctly because the whole
    literal body is dropped, braces included. Verbatim strings are not, which
    is what guard_unsupported_syntax exists to prevent reaching here.
    """
    out, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c == "/" and i + 1 < n and line[i + 1] == "/":
            break
        if c in ('"', "'"):
            quote = c
            i += 1
            while i < n:
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


@dataclass
class Region:
    id: str
    file: str
    path: Path
    anchor: str
    kind: str
    start_line: int  # 0-based, inclusive
    end_line: int  # 0-based, inclusive
    text: str
    note: str = ""

    @property
    def lines_1based(self) -> str:
        return f"{self.start_line + 1}-{self.end_line + 1}"


def find_region(lines: List[str], anchor: str, kind: str = "decl") -> Tuple[int, int]:
    """Return 0-based inclusive (start_line, end_line) for `anchor`.

    kind="decl"  -- the anchor line through its matching closing brace
    kind="line"  -- only the line the anchor appears on

    A plain anchor matches as a substring; an anchor prefixed "re:" is a regex.
    Either way the match must be unique -- an ambiguous anchor is an error,
    never a silent first-hit, because the wrong region would be rewritten with
    no signal that anything was off.
    """
    if anchor.startswith("re:"):
        pat: Optional[re.Pattern] = re.compile(anchor[3:])
        hits = [i for i, ln in enumerate(lines) if pat.search(ln)]
    else:
        hits = [i for i, ln in enumerate(lines) if anchor in ln]
    if not hits:
        raise RegionError(f"anchor not found: {anchor!r}")
    if len(hits) > 1:
        preview = "; ".join(lines[i].strip()[:60] for i in hits[:4])
        raise RegionError(f"anchor not unique ({len(hits)} hits): {anchor!r} -> {preview}")

    start = hits[0]
    if kind == "line":
        return start, start

    depth, seen_open = 0, False
    for i in range(start, len(lines)):
        for ch in strip_code(lines[i]):
            if ch == "{":
                depth += 1
                seen_open = True
            elif ch == "}":
                depth -= 1
                if seen_open and depth == 0:
                    return start, i
    raise RegionError(f"unbalanced braces from anchor: {anchor!r}")


def extract(repo: Path, specs: List[Dict[str, Any]]) -> List[Region]:
    """Resolve every region spec in a ticket against the current tree."""
    out: List[Region] = []
    for spec in specs:
        path = repo / spec["file"]
        if not path.exists():
            raise RegionError(f"{spec['id']}: file does not exist: {spec['file']}")
        language_for(path)
        src = path.read_text(encoding="utf-8")
        guard_unsupported_syntax(path, src)
        lines = src.splitlines()
        kind = spec.get("kind", "decl")
        # The old ticket schema said kind="method"/"block"; both meant the same
        # brace-matched extent that kind="decl" now means.
        if kind in ("method", "block"):
            kind = "decl"
        start, end = find_region(lines, spec["anchor"], kind)
        text = "\n".join(lines[start : end + 1])
        out.append(
            Region(
                id=spec["id"],
                file=spec["file"],
                path=path,
                anchor=spec["anchor"],
                kind=kind,
                start_line=start,
                end_line=end,
                text=text,
                note=spec.get("note", ""),
            )
        )
    return out


def apply(regions: List[Region], blocks: Dict[str, str]) -> List[str]:
    """Splice replacements in, per file, bottom-up so earlier spans stay valid.

    Returns the `file` field of every region whose file was modified. A block
    identical to the original is skipped, so an unchanged region never dirties
    the file -- which keeps the worktree diff honest about what a ticket did.
    """
    touched: List[str] = []
    by_file: Dict[Path, List[Region]] = {}
    for r in regions:
        by_file.setdefault(r.path, []).append(r)
    for path, regs in by_file.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        changed = False
        for r in sorted(regs, key=lambda x: x.start_line, reverse=True):
            body = blocks.get(r.id)
            if body is None or body.rstrip() == r.text.rstrip():
                continue
            lines[r.start_line : r.end_line + 1] = body.splitlines()
            changed = True
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            touched.append(regs[0].file)
    return touched
