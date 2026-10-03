"""Split markdown documents into prose, inline-code and fenced-code regions."""
from __future__ import annotations

import re

from ai_untell.types import Segment

_FENCE_LINE = re.compile(r"(?m)^(?P<indent>[ \t]*)(?P<marker>`{3,}|~{3,})(?P<info>[^\n]*)$")
_INLINE_CODE = re.compile(r"`[^`\n]+`")


def split_markdown(text: str) -> list[Segment]:
    """Return a list of Segments covering the whole document.

    Segment kinds: ``prose``, ``code_span``, ``code_block``.
    """
    segments: list[Segment] = []
    pos = 0
    n = len(text)

    # First pass: locate fenced code blocks line by line (CommonMark rules:
    # the closing fence uses the same character and is at least as long as
    # the opening one; an unclosed fence runs to the end of the document).
    fence_spans: list[tuple[int, int, str]] = []  # (start, end, info)
    lines = text.split("\n")
    offset = 0
    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_start = 0
    fence_info = ""
    for line in lines:
        stripped = line.strip()
        if not in_fence:
            m = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
            if m:
                in_fence = True
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                fence_info = m.group(2).strip()
                fence_start = offset
        elif (
            len(stripped) >= fence_len
            and stripped.startswith(fence_char * fence_len)
            and set(stripped) == {fence_char}
        ):
            end = offset + len(line)
            fence_spans.append((fence_start, end, fence_info))
            in_fence = False
        offset += len(line) + 1
    if in_fence:
        fence_spans.append((fence_start, n, fence_info))

    for start, end, _info in fence_spans:
        if start > pos:
            _add_prose(segments, text, pos, start)
        segments.append(Segment("code_block", start, min(end, n)))
        pos = min(end, n)
    if pos < n:
        _add_prose(segments, text, pos, n)

    return segments


def _add_prose(segments: list[Segment], text: str, start: int, end: int) -> None:
    """Add a prose region, carving out inline code spans."""
    cursor = start
    for m in _INLINE_CODE.finditer(text, start, end):
        if m.start() > cursor:
            segments.append(Segment("prose", cursor, m.start()))
        segments.append(Segment("code_span", m.start(), m.end()))
        cursor = m.end()
    if cursor < end:
        segments.append(Segment("prose", cursor, end))


def fence_language(text: str, span_start: int) -> str | None:
    """Return the language tag of the fenced block starting at ``span_start``."""
    line_end = text.find("\n", span_start)
    line = text[span_start: line_end if line_end != -1 else len(text)]
    m = re.match(r"^\s*(?:`{3,}|~{3,})\s*([\w+-]+)?", line)
    if m and m.group(1):
        return m.group(1).lower()
    return None
