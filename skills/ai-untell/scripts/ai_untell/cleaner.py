"""Rule-based cleaner: removes AI tells from text, markdown and code."""
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
    GENERATED_BY_RE,
    INLINE_CODE_RE,
    OPENER_PATTERNS,
    is_dash_double_hyphen,
)
from ai_untell.patterns.loader import STRENGTH_ORDER, PatternEngine
from ai_untell.scanner import Scanner, _EXT_TO_LANG_TAG
from ai_untell.types import (
    CleanResult,
    Config,
    ContentKind,
    LanguageId,
)
from ai_untell.unicode_ops import latin_ratio, normalize_homoglyphs, strip_invisible

# An em dash with text on both sides of the same line, spaced ("a — b") or
# not ("a—b"). A dash opening a line (dialogue, attributions) is left alone.
EM_DASH = re.compile(r"(?<=\S)[ \t]*\u2014[ \t]*(?=\S)")
EM_DASH_NEXT = re.compile(r"(?<=\S)[ \t]*\u2014[ \t]*(\S)")
EM_DASH_PAIR = re.compile(
    r"(?<=\S)[ \t]*\u2014[ \t]*([^\u2014\n.!?]{1,120}?)[ \t]*\u2014[ \t]*(?=\S)"
)
DOUBLE_EM = re.compile(r"\u2014{2,}")
# Runs of spaces between words (never leading indentation or the two trailing
# spaces of a markdown hard line break).
_INNER_SPACES = re.compile(r"(?<=\S)[ \t]{2,}(?=\S)")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")
_CUTOFF_SPLIT = re.compile(r"(?<=[.!?])(\s+)(?=[A-Z\"'(])")

NOT_ONLY_RE = re.compile(
    r"\bnot only\s+(?P<x>[^,.;:!?\n]{3,80}?),?\s+but (?:also|even)\s+"
    r"(?P<y>[^,.;:!?\n]{3,80})",
    re.IGNORECASE,
)
NOT_JUST_RE = re.compile(
    r"\bit(?:'s| is) not just (?P<ab>about )?(?P<x>[^,.;:!?\n]{3,80}?),\s+"
    r"(?:but )?it(?:'s| is) (?P=ab)?(?P<y>[^,.;:!?\n]{3,80})",
    re.IGNORECASE,
)

_VOWELS = "aeiou"
_NO_INFLECT = {"is", "are", "was", "were", "has", "have", "do", "does"}

# Matched words that look inflected (-ed/-ing) but are plain adjectives;
# their replacements must never be re-inflected.
_NO_INFLECT_MATCHES = {
    "multifaceted", "seamless", "holistic", "comprehensive", "meticulous",
    "intricate", "vibrant", "bustling", "robust", "pivotal", "crucial",
    "vital", "paramount", "profound", "enduring", "cherished", "innovative",
    "groundbreaking", "unparalleled", "unwavering", "ever-evolving",
    "fast-paced", "cutting-edge", "user-friendly", "next-generation",
    "best-in-class", "world-class", "state-of-the-art", "deep-seated",
    "nuanced", "underrated", "beloved", "treasured", "time-tested",
}


def _bump(stats: dict, key: str, n: int = 1) -> None:
    if n:
        stats[key] = stats.get(key, 0) + n


def _apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    for start, end, repl in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:start] + repl + text[end:]
    return text


def _match_case(matched: str, replacement: str) -> str:
    if matched.isupper() and len(matched) > 1:
        return replacement.upper()
    if matched[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _suffix_of(matched: str) -> str | None:
    m = matched.lower()
    if m in _NO_INFLECT_MATCHES:
        return None
    if m.endswith("ing") and len(m) > 4:
        return "ing"
    if m.endswith("ed") and len(m) > 3:
        return "ed"
    if m.endswith("ies") and len(m) > 4:
        return "ies"
    if m.endswith("s") and not m.endswith("ss") and len(m) > 2:
        if m.endswith(("ses", "xes", "zes", "ches", "shes")):
            return "es"
        return "s"
    return None


def _cvc(word: str) -> bool:
    if len(word) < 3:
        return False
    a, b, c = word[-3], word[-2], word[-1]
    return (
        a not in _VOWELS and b in _VOWELS and c not in _VOWELS and c not in "wxy"
    )


def _inflect_head(head: str, suffix: str | None) -> str:
    if suffix is None or head in _NO_INFLECT:
        return head
    h = head.lower()
    if suffix == "ing":
        if h.endswith("e") and not h.endswith("ee"):
            return h[:-1] + "ing"
        if _cvc(h):
            return h + h[-1] + "ing"
        return h + "ing"
    if suffix == "ed":
        if h.endswith("y") and len(h) > 1 and h[-2] not in _VOWELS:
            return h[:-1] + "ied"
        if h.endswith("e"):
            return h + "d"
        if _cvc(h):
            return h + h[-1] + "ed"
        return h + "ed"
    if suffix in ("s", "es"):
        if h.endswith("y") and len(h) > 1 and h[-2] not in _VOWELS:
            return h[:-1] + "ies"
        if h.endswith(("s", "x", "z", "ch", "sh")):
            return h + "es"
        return h + "s"
    if suffix == "ies":
        if h.endswith("y"):
            return h[:-1] + "ies"
        return h + "s"
    return head


def inflect_replacement(matched: str, replacement: str) -> str:
    """Inflect a lemma-form replacement to match the matched word's form."""
    suffix = _suffix_of(matched)
    parts = replacement.split(" ", 1)
    head = _inflect_head(parts[0], suffix)
    out = head if len(parts) == 1 else head + " " + parts[1]
    return _match_case(matched, out)


def _capitalize_first(s: str) -> str:
    for i, ch in enumerate(s):
        if ch.isalpha():
            return s[:i] + ch.upper() + s[i + 1 :]
    return s


class Cleaner:
    """Applies deterministic rule-based cleaning to remove AI tells."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.engine = PatternEngine().load()

    # -- top-level -----------------------------------------------------------

    def clean(
        self,
        text: str,
        content_kind: ContentKind | None = None,
        language: LanguageId | None = None,
        path: Path | None = None,
    ) -> CleanResult:
        stats: dict[str, int] = {}
        kind = content_kind or detect_content_kind(text, path)
        lang = language or detect_language(text, path)

        work = text
        if self.config.strip_invisible_unicode:
            work, counts = strip_invisible(
                work, strip_variation_selectors=self.config.strip_variation_selectors
            )
            _bump(stats, "invisible_removed", sum(counts.values()))

        if self.config.normalize_homoglyphs and latin_ratio(work) >= 0.6:
            work, n = normalize_homoglyphs(work)
            _bump(stats, "homoglyphs_fixed", n)

        if kind in (ContentKind.MARKDOWN, ContentKind.MIXED):
            work = self._clean_markdown(work, stats)
        elif kind == ContentKind.CODE:
            work = self._clean_code(work, lang, stats)
        else:
            work = self._clean_plain(work, stats)

        report = Scanner(self.config).scan(work, kind, lang, path)
        return CleanResult(
            original=text,
            cleaned=work,
            diff_stats=stats,
            remaining_hits=report.hits,
            pass_count=1,
            mode="rules",
        )

    # -- content-kind dispatch ------------------------------------------------

    def _clean_markdown(self, text: str, stats: dict) -> str:
        pieces: list[str] = []
        for segment in split_markdown(text):
            chunk = text[segment.start : segment.end]
            if segment.kind == "prose":
                pieces.append(self._clean_prose(chunk, stats))
            elif segment.kind == "code_block":
                tag = fence_language(text, segment.start)
                lang = _EXT_TO_LANG_TAG.get(tag or "", LanguageId.UNKNOWN)
                pieces.append(self._clean_code(chunk, lang, stats))
            else:  # code_span: leave untouched
                pieces.append(chunk)
        return "".join(pieces)

    def _clean_plain(self, text: str, stats: dict) -> str:
        return self._clean_prose(text, stats)

    # -- prose cleaning --------------------------------------------------------

    def _clean_prose(self, text: str, stats: dict) -> str:
        if self.config.remove_chatbot_openers:
            text = self._strip_openers(text, stats)
        if self.config.remove_knowledge_cutoff:
            text = self._strip_cutoff_sentences(text, stats)
        if self.config.remove_chatbot_closers:
            text = self._strip_closers(text, stats)
        text = self._apply_rule_replacements(text, "prose", stats)
        text = self._simplify_parallelism(text, stats)
        text = self._fix_dashes(text, stats)
        text = self._fix_curly_quotes(text, stats)
        if self.config.strip_emoji:
            text = self._strip_emoji(text, stats)
        if self.config.bold_policy == "remove":
            text = self._strip_bold(text, stats)
        return text

    # -- code cleaning ----------------------------------------------------------

    def _clean_code(self, text: str, lang: LanguageId, stats: dict) -> str:
        # Remove "Generated by <AI>" attribution lines.
        text, n = GENERATED_BY_RE.subn("", text)
        _bump(stats, "generated_by_removed", n)

        spec = get_spec(lang)
        segments = extract_segments(text, spec)
        edits: list[tuple[int, int, str]] = []
        for segment in segments:
            content = text[segment.content_start : segment.content_end]
            if not content.strip():
                continue
            if segment.kind == "string" and self.config.preserve_code_strings:
                continue  # program data: flags, regexes, keys, SQL...
            cleaned = self._clean_nl_segment(content, stats)
            if cleaned != content:
                edits.append((segment.content_start, segment.content_end, cleaned))
        return _apply_edits(text, edits)

    def _clean_nl_segment(self, text: str, stats: dict) -> str:
        text = self._apply_rule_replacements(text, "code_nl", stats)
        text = self._fix_dashes(text, stats)
        if self.config.strip_emoji:
            text = self._strip_emoji(text, stats)
        return text


    # -- replacement engine ----------------------------------------------------

    def _apply_rule_replacements(self, text: str, scope: str, stats: dict) -> str:
        strength = STRENGTH_ORDER.get(self.config.synonym_strength, 1)
        if strength <= 0:
            return text
        candidates = [
            rule for rule in self.engine.detectable(scope)
            if rule.action == "replace"
            and rule.replacements
            and STRENGTH_ORDER.get(rule.min_strength, 1) <= strength
        ]
        if not candidates:
            return text

        matches: list[tuple[int, int, object, str]] = []
        for rule in candidates:
            for m in rule.regex.finditer(text):
                if m.group(0):
                    matches.append((m.start(), m.end(), rule, m.group(0)))
        matches.sort(key=lambda t: (t[0], -(t[1] - t[0])))

        chosen: list[tuple[int, int, object, str]] = []
        last_end = -1
        for start, end, rule, matched in matches:
            if start < last_end:
                continue
            chosen.append((start, end, rule, matched))
            last_end = end

        counters: dict[str, int] = {}
        edits: list[tuple[int, int, str]] = []
        for start, end, rule, matched in chosen:
            idx = counters.get(rule.id, 0)
            replacement = rule.replacements[idx % len(rule.replacements)]
            counters[rule.id] = idx + 1
            replacement = inflect_replacement(matched, replacement)
            edits.append((start, end, replacement))
            _bump(stats, f"replaced_{rule.category.value}")
        return _apply_edits(text, edits)

    # -- chatbot artifacts -----------------------------------------------------

    def _strip_openers(self, text: str, stats: dict) -> str:
        changed = True
        max_passes = 3
        passes = 0
        while changed and passes < max_passes:
            changed = False
            passes += 1
            for pattern in OPENER_PATTERNS:
                m = pattern.match(text.lstrip())
                if m:
                    leading = text[: len(text) - len(text.lstrip())]
                    remainder = text.lstrip()[m.end():]
                    _bump(stats, "openers_removed")
                    text = leading + _capitalize_first(remainder.lstrip())
                    changed = True
                    break
        return text

    def _strip_closers(self, text: str, stats: dict) -> str:
        stripped = text.rstrip()
        for pattern in CLOSER_PATTERNS:
            m = pattern.search(stripped)
            if m:
                _bump(stats, "closers_removed")
                result = stripped[: m.start()].rstrip()
                trailing = text[len(stripped):]
                return result + trailing
        return text

    def _strip_cutoff_sentences(self, text: str, stats: dict) -> str:
        parts = _CUTOFF_SPLIT.split(text)
        out: list[str] = []
        i = 0
        while i < len(parts):
            sentence = parts[i]
            sep = parts[i + 1] if i + 1 < len(parts) else ""
            if CUTOFF_RE.search(sentence):
                _bump(stats, "cutoff_removed")
            else:
                out.append(sentence + sep)
            i += 2
        return "".join(out)

    # -- parallelism -----------------------------------------------------------

    def _simplify_parallelism(self, text: str, stats: dict) -> str:
        def fix_not_only(m: re.Match) -> str:
            x = m.group("x").strip().rstrip(",")
            y = m.group("y").strip()
            if len(x.split()) <= 8 and len(y.split()) <= 8:
                _bump(stats, "parallelism_simplified")
                return f"{x} and {y}"
            return m.group(0)

        text = NOT_ONLY_RE.sub(fix_not_only, text)

        def fix_not_just(m: re.Match) -> str:
            x = m.group("x").strip().rstrip(",")
            y = m.group("y").strip()
            ab = m.group("ab") or ""
            if len(x.split()) <= 8 and len(y.split()) <= 8:
                _bump(stats, "parallelism_simplified")
                lead = "It's" if m.group(0)[0].isupper() else "it's"
                return f"{lead} {ab}{x} and {y}"
            return m.group(0)

        return NOT_JUST_RE.sub(fix_not_just, text)


    # -- dashes and quotes -----------------------------------------------------

    def _fix_dashes(self, text: str, stats: dict) -> str:
        policy = self.config.em_dash_policy
        if policy != "keep" and "\u2014" in text:
            text, n = DOUBLE_EM.subn("\u2014", text)
            _bump(stats, "double_em_dash_fixed", n)

            if policy == "parens":
                def to_parens(m: re.Match) -> str:
                    _bump(stats, "em_dash_replaced", 2)
                    return f" ({m.group(1).strip()}) "

                text = EM_DASH_PAIR.sub(to_parens, text)

            if policy == "period":
                def to_period(m: re.Match) -> str:
                    _bump(stats, "em_dash_replaced")
                    return ". " + m.group(1).upper()

                text = EM_DASH_NEXT.sub(to_period, text)
            else:
                repl = " " if policy == "strip" else ", "  # auto / comma / parens leftovers

                def to_single(m: re.Match) -> str:
                    _bump(stats, "em_dash_replaced")
                    return repl

                text = EM_DASH.sub(to_single, text)

        dpolicy = self.config.double_dash_policy
        if dpolicy != "keep":
            if dpolicy == "en_dash":
                repl = "\u2013"
            elif dpolicy == "em_dash":
                repl = "\u2014"
            else:  # remove
                repl = ""
            # Protect HTML comments and inline code spans.
            protected: list[str] = []

            def stash(m: re.Match) -> str:
                protected.append(m.group(0))
                return f"\x00{len(protected) - 1}\x00"

            work = HTML_COMMENT_RE.sub(stash, text)
            work = INLINE_CODE_RE.sub(stash, work)
            count = 0

            def fix_double(m: re.Match) -> str:
                nonlocal count
                if not is_dash_double_hyphen(work, m):
                    return m.group(0)  # CLI flag or table separator
                count += 1
                return repl

            work = DOUBLE_HYPHEN_RE.sub(fix_double, work)
            if protected:
                work = re.sub(
                    r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], work
                )
            _bump(stats, "double_dash_fixed", count)
            text = work
        return text

    def _fix_curly_quotes(self, text: str, stats: dict) -> str:
        if self.config.curly_quotes != "straighten":
            return text
        mapping = {
            "\u201c": '"', "\u201d": '"',
            "\u2018": "'", "\u2019": "'",
        }
        count = 0
        out = []
        for ch in text:
            if ch in mapping:
                out.append(mapping[ch])
                count += 1
            else:
                out.append(ch)
        _bump(stats, "curly_quotes_fixed", count)
        return "".join(out)

    # -- emoji and bold ---------------------------------------------------------

    def _strip_emoji(self, text: str, stats: dict) -> str:
        new_text, n = EMOJI_RE.subn("", text)
        if n:
            _bump(stats, "emoji_removed", n)
            new_text = _INNER_SPACES.sub(" ", new_text)
        return new_text

    def _strip_bold(self, text: str, stats: dict) -> str:
        new_text, n = BOLD_RE.subn(r"\1", text)
        _bump(stats, "bold_flattened", n)
        return new_text
