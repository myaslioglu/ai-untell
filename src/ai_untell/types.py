"""Core data types for ai-untell."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ContentKind(str, Enum):
    """Kind of document being processed."""

    PLAIN = "plain"          # plain text, no markup
    MARKDOWN = "markdown"    # markdown prose (may contain inline code spans)
    CODE = "code"            # a source code file
    MIXED = "mixed"          # markdown containing fenced code blocks


class LanguageId(str, Enum):
    """Programming language of a code document."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    UNKNOWN = "unknown"


class TellCategory(str, Enum):
    """Category of an AI writing tell."""

    DASH_OVERUSE = "dash_overuse"
    AI_VOCAB = "ai_vocab"
    COPULA_AVOIDANCE = "copula_avoidance"
    RULE_OF_THREE = "rule_of_three"
    NEGATIVE_PARALLELISM = "negative_parallelism"
    CHATBOT_OPENER = "chatbot_opener"
    KNOWLEDGE_CUTOFF = "knowledge_cutoff"
    PROMOTIONAL = "promotional"
    SIGNIFICANCE_INFLATION = "significance_inflation"
    INVISIBLE_UNICODE = "invisible_unicode"
    HOMOGLYPH = "homoglyph"
    EMOJI_FORMATTING = "emoji_formatting"
    BOLD_OVERUSE = "bold_overuse"
    CURLY_QUOTES = "curly_quotes"
    STRUCTURAL = "structural"


@dataclass
class TellHit:
    """A single detected AI tell."""

    category: TellCategory
    span: tuple[int, int]
    matched: str
    severity: int
    rule_id: str
    suggestion: str | None = None

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "start": self.span[0],
            "end": self.span[1],
            "matched": self.matched,
            "severity": self.severity,
            "rule_id": self.rule_id,
            "suggestion": self.suggestion,
        }


@dataclass
class ScanReport:
    """Result of scanning a document."""

    content_kind: ContentKind
    language: LanguageId
    char_count: int = 0
    token_count: int = 0
    hits: list[TellHit] = field(default_factory=list)
    per_category: dict[TellCategory, int] = field(default_factory=dict)
    invisible_chars: dict[str, int] = field(default_factory=dict)
    homoglyph_count: int = 0
    ai_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "content_kind": self.content_kind.value,
            "language": self.language.value,
            "char_count": self.char_count,
            "token_count": self.token_count,
            "ai_score": self.ai_score,
            "per_category": {k.value: v for k, v in self.per_category.items()},
            "invisible_chars": self.invisible_chars,
            "homoglyph_count": self.homoglyph_count,
            "hit_count": len(self.hits),
            "hits": [h.to_dict() for h in self.hits],
        }


@dataclass
class Config:
    """Behaviour configuration for scanning/cleaning/humanizing."""

    # Dash policies
    em_dash_policy: Literal["auto", "keep", "comma", "period", "parens", "strip"] = "auto"
    double_dash_policy: Literal["en_dash", "em_dash", "keep", "remove"] = "en_dash"

    # Unicode hygiene
    strip_invisible_unicode: bool = True
    normalize_homoglyphs: bool = True
    strip_variation_selectors: bool = False

    # Formatting tells
    strip_emoji: bool = False
    curly_quotes: Literal["keep", "straighten"] = "keep"
    bold_policy: Literal["keep", "remove"] = "keep"

    # Chatbot artifacts
    remove_chatbot_openers: bool = True
    remove_chatbot_closers: bool = True
    remove_knowledge_cutoff: bool = True

    # Rule-based rewriting
    synonym_strength: Literal["off", "light", "moderate", "aggressive"] = "light"

    # Code handling
    preserve_code_identifiers: bool = True
    preserve_code_strings: bool = False

    # LLM humanizer layer
    use_llm: bool = False
    llm_provider: Literal["anthropic", "openai", "ollama"] = "anthropic"
    llm_model: str | None = None

    # Scoring
    ai_score_threshold: float = 0.5


@dataclass
class CleanResult:
    """Result of a cleaning/humanizing run."""

    original: str
    cleaned: str
    diff_stats: dict[str, int]
    remaining_hits: list[TellHit]
    pass_count: int
    mode: Literal["rules", "llm", "hybrid"]

    def to_dict(self) -> dict:
        return {
            "diff_stats": self.diff_stats,
            "remaining_hit_count": len(self.remaining_hits),
            "remaining_hits": [h.to_dict() for h in self.remaining_hits],
            "pass_count": self.pass_count,
            "mode": self.mode,
            "cleaned": self.cleaned,
        }


@dataclass
class Segment:
    """A contiguous region of a document."""

    kind: str  # "prose" | "code_span" | "code_block"
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start
