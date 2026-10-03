"""Language and content-kind detection."""
from __future__ import annotations

import re
from pathlib import Path

from ai_untell.types import ContentKind, LanguageId

EXT_TO_LANG: dict[str, LanguageId] = {
    ".py": LanguageId.PYTHON, ".pyi": LanguageId.PYTHON,
    ".js": LanguageId.JAVASCRIPT, ".jsx": LanguageId.JAVASCRIPT,
    ".mjs": LanguageId.JAVASCRIPT, ".cjs": LanguageId.JAVASCRIPT,
    ".ts": LanguageId.TYPESCRIPT, ".tsx": LanguageId.TYPESCRIPT,
    ".go": LanguageId.GO,
    ".rs": LanguageId.RUST,
    ".java": LanguageId.JAVA,
    ".cs": LanguageId.CSHARP,
    ".c": LanguageId.CPP, ".h": LanguageId.CPP, ".cc": LanguageId.CPP,
    ".cpp": LanguageId.CPP, ".cxx": LanguageId.CPP, ".hpp": LanguageId.CPP,
    ".hh": LanguageId.CPP,
}

MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}

CODE_EXTENSIONS = set(EXT_TO_LANG) | {
    ".rb", ".php", ".swift", ".kt", ".kts", ".scala", ".sh", ".bash", ".zsh",
    ".pl", ".lua", ".r", ".dart", ".ex", ".exs", ".sql", ".yaml", ".yml",
    ".toml", ".json", ".xml", ".html", ".css", ".vue", ".svelte",
}

TEXT_EXTENSIONS = {".txt", ".text", ".rst", ".adoc", ".tex"}

_FENCE_MARKER = ("```", "~~~")

# Line-anchored syntax probes. Bare words such as "from", "class" or
# "function" are common in English prose, so a probe only fires on real
# syntax at the start of a line.
_PY_DEF = re.compile(r"(?m)^[ \t]*(?:async[ \t]+)?def[ \t]+\w+[ \t]*\(")
_PY_IMPORT = re.compile(r"(?m)^(?:import[ \t]+[\w.]+|from[ \t]+[\w.]+[ \t]+import[ \t])")
_PY_CLASS = re.compile(r"(?m)^class[ \t]+\w+[ \t]*[:(]")
_GO_PACKAGE = re.compile(r"(?m)^package[ \t]+\w+[ \t]*$")
_GO_FUNC = re.compile(r"(?m)^func[ \t]+(?:\([^)]*\)[ \t]*)?\w+[ \t]*\(")
_RUST_FN = re.compile(r"(?m)^[ \t]*(?:pub(?:\([^)]*\))?[ \t]+)?fn[ \t]+\w+")
_RUST_USE = re.compile(r"(?m)^use[ \t]+(?:std|crate|super)::")
_C_INCLUDE = re.compile(r"(?m)^#[ \t]*include[ \t]*[<\"]")
_JAVA_CLASS = re.compile(r"(?m)^[ \t]*(?:public|private|protected)[ \t]+(?:static[ \t]+)?"
                         r"(?:final[ \t]+)?(?:class|interface|void)[ \t]+\w+")
_JS_FUNC = re.compile(r"(?m)^[ \t]*(?:export[ \t]+)?(?:async[ \t]+)?"
                      r"function[ \t]*\*?[ \t]*\w*[ \t]*\(")
_JS_MODULE = re.compile(r"(?m)^(?:const|let|var)[ \t]+\w+[ \t]*=[ \t]*require\("
                        r"|^import[ \t].*[ \t]from[ \t]+['\"]"
                        r"|^export[ \t]+(?:default|const|function|class)")
_CODE_PROBES = (
    _PY_DEF, _PY_IMPORT, _PY_CLASS, _GO_PACKAGE, _GO_FUNC, _RUST_FN, _RUST_USE,
    _C_INCLUDE, _JAVA_CLASS, _JS_FUNC, _JS_MODULE,
)


def detect_language(text: str, path: Path | None = None) -> LanguageId:
    """Detect the programming language from extension, shebang or content."""
    if path is not None:
        lang = EXT_TO_LANG.get(path.suffix.lower())
        if lang is not None:
            return lang

    first_line = text.split("\n", 1)[0] if text else ""
    if first_line.startswith("#!"):
        if "python" in first_line:
            return LanguageId.PYTHON
        if "node" in first_line:
            return LanguageId.JAVASCRIPT
        if "bash" in first_line or "sh" in first_line:
            return LanguageId.UNKNOWN

    head = text[:4000]
    if _PY_DEF.search(head) and (_PY_IMPORT.search(head) or _PY_CLASS.search(head)):
        return LanguageId.PYTHON
    if _GO_PACKAGE.search(head) and _GO_FUNC.search(head):
        return LanguageId.GO
    if _RUST_FN.search(head) and (_RUST_USE.search(head) or "fn main(" in head):
        return LanguageId.RUST
    if _C_INCLUDE.search(head):
        return LanguageId.CPP
    if _JAVA_CLASS.search(head):
        return LanguageId.JAVA
    if _JS_FUNC.search(head) or _JS_MODULE.search(head):
        return LanguageId.JAVASCRIPT
    if _PY_IMPORT.search(head) or _PY_DEF.search(head):
        return LanguageId.PYTHON
    return LanguageId.UNKNOWN


def detect_content_kind(text: str, path: Path | None = None) -> ContentKind:
    """Detect whether a document is prose, markdown, code or mixed."""
    if path is not None:
        suffix = path.suffix.lower()
        if suffix in MARKDOWN_EXTENSIONS:
            if "```" in text or "~~~" in text:
                return ContentKind.MIXED
            return ContentKind.MARKDOWN
        if suffix in CODE_EXTENSIONS:
            return ContentKind.CODE
        if suffix in TEXT_EXTENSIONS:
            return ContentKind.PLAIN

    if any(marker in text for marker in _FENCE_MARKER):
        return ContentKind.MIXED
    if text.startswith("#!") or detect_language(text) is not LanguageId.UNKNOWN:
        # Only treat as code when there is a strong language signal.
        if text.startswith("#!") or _looks_like_code(text):
            return ContentKind.CODE
    if _looks_like_markdown(text):
        return ContentKind.MARKDOWN
    return ContentKind.PLAIN


def _looks_like_code(text: str) -> bool:
    head = text[:4000]
    signals = sum(1 for probe in _CODE_PROBES if probe.search(head))
    return signals >= 2


def _looks_like_markdown(text: str) -> bool:
    head = text[:4000]
    headings = len(re.findall(r"(?m)^#{1,6}\s+\S", head))
    bolds = head.count("**")
    links = len(re.findall(r"\[[^\]]+\]\([^)]+\)", head))
    return headings >= 1 or bolds >= 4 or links >= 2
