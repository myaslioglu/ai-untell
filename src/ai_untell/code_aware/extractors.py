"""Extract natural-language segments (comments, docstrings, strings) from code.

A small state-machine scanner with per-language specs. This is intentionally
regex-free so that string escapes and nested constructs are handled reliably.
Identifiers and code syntax are never reported as natural-language content.
"""
from __future__ import annotations

from dataclasses import dataclass

from ai_untell.types import LanguageId


@dataclass
class CodeSegment:
    """A natural-language region inside source code.

    ``start``/``end`` cover the full construct (delimiters included);
    ``content_start``/``content_end`` cover only the editable text inside.
    """

    kind: str  # "line_comment" | "block_comment" | "string"
    start: int
    end: int
    content_start: int
    content_end: int


@dataclass(frozen=True)
class LangSpec:
    line_comments: tuple[str, ...] = ()
    block_comments: tuple[tuple[str, str], ...] = ()
    string_quotes: tuple[str, ...] = ()
    triple_quotes: bool = False
    raw_backtick: bool = False          # backtick string without escapes (Go)
    template_literal: bool = False      # backtick with ${} interpolation (JS/TS)
    rust_raw_strings: bool = False
    char_literals: bool = False         # single-quote char literals (Rust/Java/C)


SPECS: dict[LanguageId, LangSpec] = {
    LanguageId.PYTHON: LangSpec(
        line_comments=("#",),
        block_comments=(),
        string_quotes=('"', "'"),
        triple_quotes=True,
    ),
    LanguageId.JAVASCRIPT: LangSpec(
        line_comments=("//",),
        block_comments=(("/*", "*/"),),
        string_quotes=('"', "'"),
        template_literal=True,
    ),
    LanguageId.TYPESCRIPT: LangSpec(
        line_comments=("//",),
        block_comments=(("/*", "*/"),),
        string_quotes=('"', "'"),
        template_literal=True,
    ),
    LanguageId.GO: LangSpec(
        line_comments=("//",),
        block_comments=(("/*", "*/"),),
        string_quotes=('"',),
        raw_backtick=True,
        char_literals=True,
    ),
    LanguageId.RUST: LangSpec(
        line_comments=("//",),
        block_comments=(("/*", "*/"),),
        string_quotes=('"',),
        rust_raw_strings=True,
    ),
    LanguageId.JAVA: LangSpec(
        line_comments=("//",),
        block_comments=(("/*", "*/"),),
        string_quotes=('"',),
        char_literals=True,
    ),
    LanguageId.CSHARP: LangSpec(
        line_comments=("//",),
        block_comments=(("/*", "*/"),),
        string_quotes=('"',),
        char_literals=True,
    ),
    LanguageId.CPP: LangSpec(
        line_comments=("//",),
        block_comments=(("/*", "*/"),),
        string_quotes=('"', "'"),
    ),
    LanguageId.UNKNOWN: LangSpec(
        line_comments=("#", "//"),
        block_comments=(("/*", "*/"),),
        string_quotes=('"', "'"),
    ),
}


def get_spec(language: LanguageId) -> LangSpec:
    return SPECS.get(language, SPECS[LanguageId.UNKNOWN])


def _ident_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def extract_segments(text: str, spec: LangSpec) -> list[CodeSegment]:
    """Scan ``text`` and return every natural-language segment."""
    segments: list[CodeSegment] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # --- line comments ---
        handled = False
        for prefix in spec.line_comments:
            if text.startswith(prefix, i):
                if prefix == "#" and i > 0 and _ident_char(text[i - 1]):
                    break  # e.g. something#tag - not a comment
                end = text.find("\n", i)
                end = n if end == -1 else end
                segments.append(
                    CodeSegment("line_comment", i, end, i + len(prefix), end)
                )
                i = end
                handled = True
                break
        if handled:
            continue

        # --- block comments ---
        for opener, closer in spec.block_comments:
            if text.startswith(opener, i):
                end = text.find(closer, i + len(opener))
                if end == -1:
                    content_end, full_end = n, n
                else:
                    content_end, full_end = end, end + len(closer)
                segments.append(
                    CodeSegment("block_comment", i, full_end, i + len(opener), content_end)
                )
                i = full_end
                handled = True
                break
        if handled:
            continue

        # --- rust raw strings: r"...", r#"..."# ---
        if spec.rust_raw_strings and ch == "r":
            prev_ch = text[i - 1] if i > 0 else " "
            if not _ident_char(prev_ch):
                j = i + 1
                hashes = 0
                while j < n and text[j] == "#":
                    hashes += 1
                    j += 1
                if j < n and text[j] == '"' and hashes <= 3:
                    closer = '"' + "#" * hashes
                    k = j + 1
                    end = n
                    while k < n:
                        if text.startswith(closer, k):
                            end = k
                            break
                        k += 1
                    segments.append(CodeSegment("string", i, end + len(closer), j + 1, end))
                    i = end + len(closer)
                    continue

        # --- triple-quoted strings (Python docstrings) ---
        if spec.triple_quotes and (text.startswith('"""', i) or text.startswith("'''", i)):
            quote = text[i : i + 3]
            j = i + 3
            end = n
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text.startswith(quote, j):
                    end = j
                    break
                j += 1
            full_end = min(end + 3, n)
            segments.append(CodeSegment("string", i, full_end, i + 3, end))
            i = full_end
            continue

        # --- template literals / backticks ---
        if ch == "`" and (spec.template_literal or spec.raw_backtick):
            if spec.template_literal:
                new_segments, new_i = _scan_template_literal(text, i, n)
                segments.extend(new_segments)
                i = new_i
            else:
                j = text.find("`", i + 1)
                if j == -1:
                    segments.append(CodeSegment("string", i, n, i + 1, n))
                    i = n
                else:
                    segments.append(CodeSegment("string", i, j + 1, i + 1, j))
                    i = j + 1
            continue

        # --- regular strings ---
        if ch in spec.string_quotes:
            i = _scan_regular_string(text, i, n, ch, spec, segments)
            continue

        i += 1

    return segments



def _scan_regular_string(
    text: str,
    i: int,
    n: int,
    ch: str,
    spec: LangSpec,
    segments: list[CodeSegment],
) -> int:
    """Scan a single/double quoted string starting at ``i``; return new index."""
    if ch == "'" and spec.char_literals:
        # Skip single-character literals like 'a' or '\n'
        if i + 2 < n and text[i + 2] == "'" and text[i + 1] != "\\":
            return i + 3
        if i + 3 < n and text[i + 1] == "\\" and text[i + 3] == "'":
            return i + 4
    j = i + 1
    end = n
    while j < n:
        cj = text[j]
        if cj == "\\":
            j += 2
            continue
        if cj == "\n":
            # Unterminated string; stop at end of line.
            end = j
            break
        if cj == ch:
            end = j
            break
        j += 1
    full_end = end + 1 if end < n else n
    segments.append(CodeSegment("string", i, full_end, i + 1, end))
    return full_end


def _scan_template_literal(text: str, i: int, n: int) -> tuple[list[CodeSegment], int]:
    """Scan a JS/TS template literal, splitting around ${...} interpolations."""
    segments: list[CodeSegment] = []
    j = i + 1
    content_start = j
    while j < n:
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "`":
            if content_start < j:
                segments.append(CodeSegment("string", i, j + 1, content_start, j))
            return segments, j + 1
        if text.startswith("${", j):
            if content_start < j:
                segments.append(CodeSegment("string", i, j, content_start, j))
            depth = 1
            k = j + 2
            while k < n and depth > 0:
                ck = text[k]
                if ck == "{":
                    depth += 1
                elif ck == "}":
                    depth -= 1
                elif ck in ("'", '"', "`"):
                    q = ck
                    k += 1
                    while k < n and text[k] != q:
                        if text[k] == "\\":
                            k += 1
                        k += 1
                k += 1
            j = k
            content_start = j
            continue
        j += 1
    if content_start < n:
        segments.append(CodeSegment("string", i, n, content_start, n))
    return segments, n
