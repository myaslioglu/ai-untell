"""Scanner: detect AI tells in text, markdown and code."""
from __future__ import annotations

import re
from pathlib import Path

from ai_untell.code_aware.extractors import extract_segments, get_spec
from ai_untell.code_aware.languages import detect_content_kind, detect_language
from ai_untell.code_aware.markdown import fence_language, split_markdown
from ai_untell.patterns.builtin import (
    CLOSER_PATTERNS,
    CUTOFF_RE,
    DOUBLE_HYPHEN_RE,
    EMOJI_RE,
    INLINE_CODE_RE,
    OPENER_PATTERNS,
    SENTENCE_SPLIT_RE,
    is_dash_double_hyphen,
)
from ai_untell.patterns.loader import PatternEngine
from ai_untell.scorer import compute_ai_score
from ai_untell.types import (
    Config,
    ContentKind,
    LanguageId,
    ScanReport,
    TellCategory,
    TellHit,
)
from ai_untell.unicode_ops import INVISIBLE_CHAR_NAMES, find_homoglyphs, find_invisible

SPACED_EM_DASH_RE = re.compile(r"\s\u2014\s")
UNSPACED_EM_DASH_RE = re.compile(r"\w\u2014\w")
DOUBLE_EM_RE = re.compile(r"\u2014{2,}")
CURLY_QUOTE_RE = re.compile("[\u201c\u201d\u2018\u2019]")
BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*")
HEADING_RE = re.compile(r"(?m)^#{1,6}\s+\S")
_INLINE_HEADER_LIST_RE = re.compile(r"(?m)^\s*[-*]\s+\*\*[^*\n]{1,60}:\*\*")

_EXT_TO_LANG_TAG = {
    "python": LanguageId.PYTHON, "py": LanguageId.PYTHON,
    "javascript": LanguageId.JAVASCRIPT, "js": LanguageId.JAVASCRIPT,
    "typescript": LanguageId.TYPESCRIPT, "ts": LanguageId.TYPESCRIPT,
    "go": LanguageId.GO, "golang": LanguageId.GO,
    "rust": LanguageId.RUST, "rs": LanguageId.RUST,
    "java": LanguageId.JAVA, "csharp": LanguageId.CSHARP, "cs": LanguageId.CSHARP,
    "c": LanguageId.CPP, "cpp": LanguageId.CPP, "c++": LanguageId.CPP,
}

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def count_tokens(text: str) -> int:
    return len(_TOKEN_RE.findall(text))


class Scanner:
    """Detects AI tells and produces a scored ScanReport."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.engine = PatternEngine().load()

    # -- public API ---------------------------------------------------------

    def scan(
        self,
        text: str,
        content_kind: ContentKind | None = None,
        language: LanguageId | None = None,
        path: Path | None = None,
    ) -> ScanReport:
        kind = content_kind or detect_content_kind(text, path)
        lang = language or detect_language(text, path)

        hits: list[TellHit] = []
        if kind in (ContentKind.MARKDOWN, ContentKind.MIXED):
            hits.extend(self._scan_markdown(text))
        elif kind == ContentKind.CODE:
            hits.extend(self._scan_code_text(text, lang))
        else:
            hits.extend(self._scan_prose(text, offset=0))

        hits.extend(self._scan_unicode(text))

        report = ScanReport(
            content_kind=kind,
            language=lang,
            char_count=len(text),
            token_count=count_tokens(text),
            hits=sorted(hits, key=lambda h: h.span[0]),
        )
        for hit in report.hits:
            report.per_category[hit.category] = report.per_category.get(hit.category, 0) + 1
        report.ai_score = compute_ai_score(report)
        return report

    # -- segment scanners ----------------------------------------------------

    def _scan_markdown(self, text: str) -> list[TellHit]:
        hits: list[TellHit] = []
        for segment in split_markdown(text):
            chunk = text[segment.start : segment.end]
            if segment.kind == "prose":
                hits.extend(self._scan_prose(chunk, offset=segment.start))
            elif segment.kind == "code_block":
                tag = fence_language(text, segment.start)
                lang = _EXT_TO_LANG_TAG.get(tag or "", LanguageId.UNKNOWN)
                hits.extend(self._scan_code_text(chunk, lang, offset=segment.start))
            # code_span: never scanned
        return hits

    def _scan_prose(self, text: str, offset: int = 0) -> list[TellHit]:
        hits = self.engine.match(text, scope="prose", offset=offset)
        hits.extend(self._scan_prose_extras(text, offset))
        hits.extend(self._scan_chatbot(text, offset))
        return hits

    def _scan_prose_extras(self, text: str, offset: int) -> list[TellHit]:
        hits: list[TellHit] = []
        # Do not flag anything inside inline code spans.
        masked = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), text)

        for m in DOUBLE_EM_RE.finditer(masked):
            hits.append(self._hit(TellCategory.DASH_OVERUSE, 2, m, offset, "DASH-101"))
        for m in SPACED_EM_DASH_RE.finditer(masked):
            hits.append(self._hit(TellCategory.DASH_OVERUSE, 2, m, offset, "DASH-102"))
        for m in UNSPACED_EM_DASH_RE.finditer(masked):
            if not any(h.span[0] <= offset + m.start() < h.span[1] for h in hits):
                hits.append(self._hit(TellCategory.DASH_OVERUSE, 1, m, offset, "DASH-103"))
        for m in DOUBLE_HYPHEN_RE.finditer(masked):
            if is_dash_double_hyphen(masked, m):
                hits.append(self._hit(TellCategory.DASH_OVERUSE, 2, m, offset, "DASH-104"))

        for m in EMOJI_RE.finditer(masked):
            hits.append(self._hit(TellCategory.EMOJI_FORMATTING, 1, m, offset, "EMOJI-101"))

        for m in CURLY_QUOTE_RE.finditer(masked):
            hits.append(self._hit(TellCategory.CURLY_QUOTES, 1, m, offset, "QUOTE-101"))

        bolds = BOLD_RE.findall(masked)
        if len(bolds) > 3:
            for m in BOLD_RE.finditer(masked):
                hits.append(self._hit(TellCategory.BOLD_OVERUSE, 1, m, offset, "BOLD-101"))

        headings = HEADING_RE.findall(masked)
        inline_headers = _INLINE_HEADER_LIST_RE.findall(masked)
        tokens = count_tokens(masked) or 1
        if len(headings) >= 4 and tokens / max(len(headings), 1) < 40:
            hits.append(
                TellHit(TellCategory.STRUCTURAL, (offset, offset + 1),
                        "heading-heavy document", 1, "STRUCT-101")
            )
        if len(inline_headers) >= 3:
            hits.append(
                TellHit(TellCategory.STRUCTURAL, (offset, offset + 1),
                        "inline-header list", 1, "STRUCT-102")
            )
        return hits

    def _scan_chatbot(self, text: str, offset: int) -> list[TellHit]:
        hits: list[TellHit] = []
        paragraphs = re.split(r"\n\s*\n", text)
        pos = 0
        for para in paragraphs:
            start = text.find(para, pos)
            pos = start + len(para)
            stripped = para.lstrip()
            lead = start + (len(para) - len(stripped))
            for pattern in OPENER_PATTERNS:
                m = pattern.match(stripped)
                if m and len(m.group(0)) < len(stripped):
                    hits.append(
                        TellHit(TellCategory.CHATBOT_OPENER,
                                (offset + lead, offset + lead + len(m.group(0))),
                                m.group(0).strip(), 3, "CHAT-101")
                    )
                    break
            for pattern in CLOSER_PATTERNS:
                m = pattern.search(para)
                if m:
                    hits.append(
                        TellHit(TellCategory.CHATBOT_OPENER,
                                (offset + start + m.start(), offset + start + m.end()),
                                m.group(0).strip(), 3, "CHAT-102")
                    )
                    break
        cursor = 0
        for sentence in SENTENCE_SPLIT_RE.split(text):
            idx = text.find(sentence, cursor)
            cursor = idx + len(sentence)
            if CUTOFF_RE.search(sentence):
                hits.append(
                    TellHit(TellCategory.KNOWLEDGE_CUTOFF,
                            (offset + idx, offset + idx + len(sentence)),
                            sentence.strip()[:80], 3, "CHAT-103")
                )
        return hits


    def _scan_code_text(
        self,
        text: str,
        lang: LanguageId,
        offset: int = 0,
    ) -> list[TellHit]:
        hits: list[TellHit] = []
        spec = get_spec(lang)
        for segment in extract_segments(text, spec):
            content = text[segment.content_start : segment.content_end]
            if not content.strip():
                continue
            if segment.kind == "string" and self.config.preserve_code_strings:
                continue
            base = offset + segment.content_start
            hits.extend(self.engine.match(content, scope="code_nl", offset=base))
            for m in EMOJI_RE.finditer(content):
                hits.append(self._hit(TellCategory.EMOJI_FORMATTING, 1, m, base, "EMOJI-102"))
            for m in SPACED_EM_DASH_RE.finditer(content):
                hits.append(self._hit(TellCategory.DASH_OVERUSE, 2, m, base, "DASH-105"))
        return hits

    def _scan_unicode(self, text: str) -> list[TellHit]:
        hits: list[TellHit] = []
        for ch, offsets in find_invisible(text).items():
            name = INVISIBLE_CHAR_NAMES.get(ch, f"U+{ord(ch):04X}")
            hits.append(
                TellHit(
                    TellCategory.INVISIBLE_UNICODE,
                    (offsets[0], offsets[-1] + 1),
                    f"{name} x{len(offsets)}",
                    3,
                    "UNI-101",
                )
            )
        for idx, ch in find_homoglyphs(text):
            hits.append(
                TellHit(
                    TellCategory.HOMOGLYPH,
                    (idx, idx + 1),
                    ch,
                    3,
                    "UNI-102",
                )
            )
        return hits

    # -- helpers --------------------------------------------------------------

    def _hit(
        self,
        category: TellCategory,
        severity: int,
        m: re.Match,
        offset: int,
        rule_id: str,
    ) -> TellHit:
        return TellHit(
            category=category,
            span=(offset + m.start(), offset + m.end()),
            matched=m.group(0),
            severity=severity,
            rule_id=rule_id,
        )
