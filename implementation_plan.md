# Implementation Plan

## Overview

**ai-untell** is a Python package and CLI that detects and removes the visible
"tells" that mark text and code as AI-generated, and optionally rewrites prose
through an LLM to disrupt ("jam") statistical token-level watermarks. It works
fully offline with a deterministic rule engine, and can layer an optional LLM
provider on top for higher-quality humanization.

The scope covers three cleaning layers over prose, markdown, and source code:

1. **Detector (Scanner + Scorer)** — finds 15 tell categories (em-dash overuse,
   AI vocabulary, copula avoidance, rule-of-three, negative parallelism, chatbot
   openers/closers, knowledge-cutoff disclaimers, promotional tone, significance
   inflation, invisible Unicode, homoglyphs, emoji, bold overuse, curly quotes,
   structural tics) and emits a weighted 0–1 AI score.
2. **Cleaner** — deterministic rule-based rewriting: replaces em dashes,
   normalizes double hyphens, substitutes stock vocabulary with case- and
   inflection-aware synonyms, removes chatbot openers/closers and cutoff
   disclaimers, strips invisible Unicode and normalizes homoglyphs.
3. **Humanizer** — optional LLM paraphrase layer (Anthropic / OpenAI / local
   Ollama) that preserves facts while rewriting prose to read naturally; falls
   back to the Cleaner when no provider is configured or a call fails.

The research that informed this plan is summarized in `RESEARCH.md`. The
critical finding: Anthropic has not publicly confirmed a production output
watermark for Claude, so the tool concentrates on removing **visible** AI tells
and **invisible steganographic carriers** (zero-width chars, tag-block chars,
homoglyphs), while the LLM paraphrase layer is what disrupts token-level
statistical watermarks (Kirchenbauer green-list, Aaronson Gumbel-max) that
cannot be reverse-engineered without model access.

## Types

All data types live in `src/ai_untell/types.py`:

- `ContentKind` (enum): `plain`, `markdown`, `code`, `mixed`.
- `LanguageId` (enum): `python`, `javascript`, `typescript`, `go`, `rust`,
  `java`, `csharp`, `cpp`, `unknown`.
- `TellCategory` (enum): the 15 categories listed above.
- `TellHit` (dataclass): `category`, `span`, `matched`, `severity`, `rule_id`,
  `suggestion`.
- `ScanReport` (dataclass): `content_kind`, `language`, `char_count`,
  `token_count`, `hits`, `per_category`, `invisible_chars`, `homoglyph_count`,
  `ai_score`.
- `Config` (dataclass): all tunables — dash policies, unicode hygiene, emoji,
  curly quotes, bold, chatbot removal, synonym strength, code handling, LLM
  settings, score threshold.
- `CleanResult` (dataclass): `original`, `cleaned`, `diff_stats`,
  `remaining_hits`, `pass_count`, `mode`.
- `Segment` (dataclass): `kind`, `start`, `end` for markdown splitting.

## Files

New files under `/Users/muratyaslioglu/.cline/data/workspaces/chat/ai-untell/`:

- `pyproject.toml`, `LICENSE`, `Makefile`, `README.md`, `RESEARCH.md`,
  `implementation_plan.md`.
- `src/ai_untell/__init__.py` — public API (`scan`, `clean`, `humanize`,
  `scan_file`, `clean_file`).
- `src/ai_untell/types.py` — data model.
- `src/ai_untell/unicode_ops.py` — invisible chars, homoglyphs, NFC.
- `src/ai_untell/scanner.py` — `Scanner` + segment dispatch.
- `src/ai_untell/scorer.py` — weighted AI score.
- `src/ai_untell/cleaner.py` — rule-based `Cleaner`.
- `src/ai_untell/humanizer.py` — LLM + fallback `Humanizer`.
- `src/ai_untell/cli.py` + `__main__.py` — Click CLI.
- `src/ai_untell/patterns/` — `builtin.py`, `loader.py`, `rules/*.yml`
  (vocab, structure, significance, promotional, code).
- `src/ai_untell/code_aware/` — `languages.py`, `extractors.py`, `markdown.py`.

## Functions

Key public functions (`src/ai_untell/__init__.py`):

- `scan(text, *, content_kind=None, language=None, config=None) -> ScanReport`
- `clean(text, *, config=None) -> CleanResult`
- `humanize(text, *, config=None) -> CleanResult`
- `scan_file(path, *, config=None) -> ScanReport`
- `clean_file(path, *, in_place=False, backup=True, config=None) -> CleanResult`

Internal helpers of note: `inflect_replacement(matched, replacement)` for
case/inflection-aware synonym substitution; `strip_invisible`,
`normalize_homoglyphs`, `latin_ratio` in `unicode_ops`; `extract_segments`,
`get_spec` in `code_aware.extractors`; `split_markdown` in
`code_aware.markdown`; `compute_ai_score` in `scorer`.

## Classes

- `Scanner` (`scanner.py`) — `scan`, `_scan_markdown`, `_scan_prose`,
  `_scan_prose_extras`, `_scan_chatbot`, `_scan_code_text`, `_scan_unicode`.
- `Cleaner` (`cleaner.py`) — `clean`, `_clean_markdown`, `_clean_prose`,
  `_clean_code`, `_clean_nl_segment`, `_apply_rule_replacements`,
  `_strip_openers`, `_strip_closers`, `_strip_cutoff_sentences`,
  `_simplify_parallelism`, `_fix_dashes`, `_fix_curly_quotes`, `_strip_emoji`,
  `_strip_bold`.
- `Humanizer` (`humanizer.py`) — `humanize`, `_humanize_with_llm`,
  `_build_prompt`, `_postprocess`, `_humanize_rules`.
- `PatternEngine` (`patterns/loader.py`) — `load`, `detectable`, `match`;
  `Rule` dataclass.
- `LLMProvider` (ABC) + `AnthropicProvider`, `OpenAIProvider`, `OllamaProvider`.
- `LangSpec` / `CodeSegment` (`code_aware/extractors.py`).

## Dependencies

Core (always): `click`, `pyyaml`, `rich`. Optional extras: `llm` (`anthropic`,
`openai`), `dev` (`pytest`, `pytest-cov`, `ruff`). Local Ollama uses the stdlib
(`urllib`), so no extra dependency. The base install has no heavy NLP
dependencies; synonym substitution uses a built-in lemma table plus a small
inflection engine, not WordNet/spaCy.

## Testing

Eight test modules cover unicode ops, the pattern engine, scanner/scoring,
cleaner, code-aware cleaning (identifier preservation), humanizer (fake LLM +
fallback), CLI (via `CliRunner`), and the public API. Fixtures include an
AI-sounding paragraph, a human paragraph, a Claude-style Python file, and a
mixed markdown document. Validation commands:

```
pytest tests/ -v
ruff check src tests
python -m ai_untell demo
python examples/demo_scan.py
python examples/demo_clean.py
```

## Implementation Order

1. Project scaffold (`pyproject.toml`, package dirs, venv, editable install).
2. `types.py` data model.
3. `unicode_ops.py` (invisible chars, homoglyphs).
4. Pattern engine + YAML rule files.
5. `code_aware` (language detection, segment extraction, markdown split).
6. `scorer.py` + `scanner.py`.
7. `cleaner.py` (rule-based pipeline).
8. `llm/` providers + `humanizer.py`.
9. `cli.py` + `__main__.py` + public API.
10. Tests + fixtures + examples; iterate until green.
11. Documentation (`README.md`, `RESEARCH.md`, this plan).

- `src/ai_untell/llm/` — `base.py`, `anthropic_provider.py`,
  `openai_provider.py`, `ollama_provider.py`.
- `tests/` — 8 test modules + fixtures.
- `examples/` — `demo_scan.py`, `demo_clean.py`.
