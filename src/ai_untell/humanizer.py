"""Humanizer: LLM-powered rewriting with rule-based fallback.

When an LLM provider is configured, the humanizer asks the model to rewrite
the text so it reads naturally, while preserving every factual claim. When no
provider is available (or the call fails), it falls back to the deterministic
rule-based Cleaner so the tool always produces output offline.
"""
from __future__ import annotations

from pathlib import Path

from ai_untell.cleaner import Cleaner
from ai_untell.code_aware.languages import detect_content_kind, detect_language
from ai_untell.llm.base import LLMProvider, get_provider
from ai_untell.scanner import Scanner
from ai_untell.types import CleanResult, Config, ContentKind, LanguageId
from ai_untell.unicode_ops import latin_ratio, normalize_homoglyphs, strip_invisible

HUMANIZE_SYSTEM_PROMPT = """\
You are a professional human editor. Rewrite the text so it reads like it was
written by a thoughtful person, not an AI assistant.

Hard rules:
1. Preserve every fact, number, name, date, quote, citation and technical
   detail. Do NOT invent, remove or alter any factual claim.
2. Remove AI writing tells: em dashes, double hyphens, stock vocabulary
   (delve, leverage, foster, harness, multifaceted, tapestry, realm, holistic,
   comprehensive, seamless, robust, pivotal, crucial, vital, testament,
   moreover, furthermore, additionally, in conclusion), copula avoidance
   ("serves as", "stands as"), negative parallelisms ("not just X, it's Y"),
   rule-of-three cadence, chatbot openers/closers, significance inflation.
3. Use plain, concrete words and varied sentence length. Mix short and long
   sentences. Prefer active voice and simple verbs.
4. Do not add headings, bullet lists, bold, emoji or marketing tone unless the
   source already uses them.
5. If the input contains code blocks or inline code, keep the code EXACTLY
   as-is. Only rewrite prose, comments and docstrings.
6. Return ONLY the rewritten text. No preamble, no explanation, no apology.
"""


class Humanizer:
    """Rewrites text to remove AI tells, using an LLM when available."""

    def __init__(
        self,
        config: Config | None = None,
        provider: LLMProvider | None = None,
    ):
        self.config = config or Config()
        self._provider = provider
        self._cleaner = Cleaner(self.config)
        self._scanner = Scanner(self.config)

    def _get_provider(self) -> LLMProvider | None:
        if self._provider is not None:
            return self._provider
        if not self.config.use_llm:
            return None
        try:
            self._provider = get_provider(self.config.llm_provider, self.config.llm_model)
            return self._provider
        except Exception:
            return None

    def humanize(
        self,
        text: str,
        content_kind: ContentKind | None = None,
        language: LanguageId | None = None,
        path: Path | None = None,
    ) -> CleanResult:
        kind = content_kind or detect_content_kind(text, path)
        lang = language or detect_language(text, path)

        provider = self._get_provider()
        if provider is not None:
            try:
                return self._humanize_with_llm(text, provider, kind, lang)
            except Exception:
                # Fall through to rule-based cleaning on any provider error.
                pass
        return self._humanize_rules(text, kind, lang)

    # -- LLM path --------------------------------------------------------------

    def _humanize_with_llm(
        self,
        text: str,
        provider: LLMProvider,
        kind: ContentKind,
        lang: LanguageId,
    ) -> CleanResult:
        stats: dict[str, int] = {}
        # Unicode hygiene is deterministic and always safe: do it first.
        work = text
        if self.config.strip_invisible_unicode:
            work, counts = strip_invisible(
                work, strip_variation_selectors=self.config.strip_variation_selectors
            )
            if sum(counts.values()):
                stats["invisible_removed"] = sum(counts.values())
        if self.config.normalize_homoglyphs and latin_ratio(work) >= 0.6:
            work, n = normalize_homoglyphs(work)
            if n:
                stats["homoglyphs_fixed"] = n

        prompt = self._build_prompt(work, kind, lang)
        rewritten = provider.rewrite(HUMANIZE_SYSTEM_PROMPT, prompt)
        rewritten = self._postprocess(rewritten)
        stats["llm_rewritten"] = 1

        report = self._scanner.scan(rewritten, kind, lang)
        return CleanResult(
            original=text,
            cleaned=rewritten,
            diff_stats=stats,
            remaining_hits=report.hits,
            pass_count=1,
            mode="llm",
        )

    def _build_prompt(self, text: str, kind: ContentKind, lang: LanguageId) -> str:
        kind_label = {
            ContentKind.PLAIN: "plain text",
            ContentKind.MARKDOWN: "markdown",
            ContentKind.CODE: f"{lang.value} source code",
            ContentKind.MIXED: "a markdown document with code blocks",
        }[kind]
        return (
            f"Rewrite the following {kind_label}. "
            "Keep all facts and all code exactly as they are.\n\n"
            f"--- BEGIN TEXT ---\n{text}\n--- END TEXT ---"
        )

    def _postprocess(self, text: str) -> str:
        # Strip a leading fence some models wrap around the whole answer.
        stripped = text.strip()
        if stripped.startswith("```") and stripped.count("```") >= 2:
            first_newline = stripped.find("\n")
            inner = stripped[first_newline + 1 :]
            last_fence = inner.rfind("```")
            if last_fence != -1:
                stripped = inner[:last_fence].rstrip()
        return stripped + "\n" if text.endswith("\n") else stripped

    # -- rule-based fallback -----------------------------------------------------

    def _humanize_rules(
        self,
        text: str,
        kind: ContentKind,
        lang: LanguageId,
    ) -> CleanResult:
        return self._cleaner.clean(text, kind, lang)
