"""Language and content-kind detection."""
from __future__ import annotations

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
    if "def " in head and ("import " in head or "from " in head):
        return LanguageId.PYTHON
    if "\npackage main" in head or head.startswith("package "):
        return LanguageId.GO
    if "fn main(" in head or "\nuse std::" in head:
        return LanguageId.RUST
    if "#include" in head:
        return LanguageId.CPP
    if "public class " in head or "private static void" in head:
        return LanguageId.JAVA
    if "function " in head or "const " in head and "require(" in head:
        return LanguageId.JAVASCRIPT
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
    signals = 0
    for probe in ("import ", "from ", "def ", "class ", "function ", "const ",
                  "package ", "#include", "fn ", "use std::", "public class "):
        if probe in head:
            signals += 1
    return signals >= 2


def _looks_like_markdown(text: str) -> bool:
    import re

    head = text[:4000]
    headings = len(re.findall(r"(?m)^#{1,6}\s+\S", head))
    bolds = head.count("**")
    links = len(re.findall(r"\[[^\]]+\]\([^)]+\)", head))
    return headings >= 1 or bolds >= 4 or links >= 2
