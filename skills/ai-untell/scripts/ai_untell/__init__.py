"""ai-untell: detect and remove AI writing tells, invisible watermarks and
chatbot artifacts from text and code.

Public API:
    scan(text) -> ScanReport
    clean(text) -> CleanResult
    humanize(text) -> CleanResult
"""
from __future__ import annotations

from pathlib import Path

from ai_untell.cleaner import Cleaner
from ai_untell.humanizer import Humanizer
from ai_untell.scanner import Scanner
from ai_untell.types import (
    CleanResult,
    Config,
    ContentKind,
    LanguageId,
    ScanReport,
    TellCategory,
    TellHit,
)

__version__ = "0.2.0"

__all__ = [
    "scan",
    "clean",
    "humanize",
    "scan_file",
    "clean_file",
    "Scanner",
    "Cleaner",
    "Humanizer",
    "Config",
    "ContentKind",
    "LanguageId",
    "ScanReport",
    "TellCategory",
    "TellHit",
    "CleanResult",
    "__version__",
]


def scan(
    text: str,
    *,
    content_kind: ContentKind | None = None,
    language: LanguageId | None = None,
    config: Config | None = None,
) -> ScanReport:
    """Scan ``text`` for AI tells and return a scored report."""
    return Scanner(config).scan(text, content_kind, language)


def clean(text: str, *, config: Config | None = None) -> CleanResult:
    """Clean ``text`` with the deterministic rule engine."""
    return Cleaner(config).clean(text)


def humanize(
    text: str,
    *,
    config: Config | None = None,
) -> CleanResult:
    """Humanize ``text`` (LLM if configured, otherwise rule-based)."""
    return Humanizer(config).humanize(text)


def scan_file(path: str | Path, *, config: Config | None = None) -> ScanReport:
    """Scan a file from disk."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return Scanner(config).scan(text, path=p)


def clean_file(
    path: str | Path,
    *,
    in_place: bool = False,
    backup: bool = True,
    config: Config | None = None,
) -> CleanResult:
    """Clean a file from disk; optionally rewrite it in place."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    result = Cleaner(config).clean(text, path=p)
    if in_place and result.cleaned != text:
        if backup:
            p.with_suffix(p.suffix + ".bak").write_text(text, encoding="utf-8")
        p.write_text(result.cleaned, encoding="utf-8")
    return result
