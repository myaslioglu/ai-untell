"""Code-aware processing: language detection and NL segment extraction."""
from ai_untell.code_aware.languages import detect_language, detect_content_kind
from ai_untell.code_aware.extractors import extract_segments, get_spec, CodeSegment
from ai_untell.code_aware.markdown import split_markdown

__all__ = [
    "detect_language",
    "detect_content_kind",
    "extract_segments",
    "get_spec",
    "CodeSegment",
    "split_markdown",
]
