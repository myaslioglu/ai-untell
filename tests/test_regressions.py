"""Regression tests: human-written text and code must survive cleaning intact."""
from pathlib import Path

import pytest

from ai_untell.cleaner import Cleaner
from ai_untell.code_aware.languages import detect_content_kind
from ai_untell.code_aware.markdown import split_markdown
from ai_untell.humanizer import Humanizer
from ai_untell.llm.base import LLMError, LLMProvider, TruncatedOutputError
from ai_untell.scanner import Scanner
from ai_untell.types import Config, ContentKind, TellCategory


def _clean(text: str, path: str | None = None, **cfg) -> str:
    return Cleaner(Config(**cfg)).clean(text, path=Path(path) if path else None).cleaned


# -- code string literals ------------------------------------------------------

def test_python_string_literals_untouched():
    code = (
        'import argparse\n'
        'p = argparse.ArgumentParser()\n'
        'p.add_argument("--in-place")\n'
        'RE = r"(?<!-)--(?!-)"\n'
        'MODE = "seamless"\n'
    )
    assert _clean(code, "x.py", synonym_strength="aggressive") == code


def test_python_docstrings_still_cleaned():
    code = 'def f():\n    """Loads data — and leverages caching."""\n    return 1\n'
    out = _clean(code, "x.py")
    assert "—" not in out
    assert "leverage" not in out


def test_strings_cleaned_when_opted_in():
    code = 'MSG = "We leverage caching."\n'
    out = _clean(code, "x.py", preserve_code_strings=False)
    assert "leverage" not in out


def test_yaml_values_and_urls_untouched():
    text = 'url: https://example.com/seamless-docs  # leverage this\nname: "seamless"\n'
    out = _clean(text, "c.yml", synonym_strength="aggressive")
    assert "https://example.com/seamless-docs" in out
    assert 'name: "seamless"' in out
    assert "leverage" not in out  # the real comment is still cleaned


# -- markdown fences -------------------------------------------------------------

def test_unclosed_fence_is_code_until_end():
    text = "Intro text.\n\n```python\nx = 'a -- b'  # note\nprint('--help')\n"
    out = _clean(text, "a.md")
    assert "x = 'a -- b'" in out
    assert "print('--help')" in out


def test_longer_fence_not_closed_by_shorter_one():
    text = "Doc.\n\n````md\n```python\nx = '--flag'\n```\n````\n\nAfter -- prose.\n"
    segments = split_markdown(text)
    blocks = [s for s in segments if s.kind == "code_block"]
    assert len(blocks) == 1
    assert text[blocks[0].start:blocks[0].end].rstrip().endswith("````")
    assert "x = '--flag'" in _clean(text, "a.md")


# -- chatbot openers / closers -------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Surely this is enough to pass the test.",
    "Absolutely nothing happened after the update.",
    "Sure enough, the build failed again.",
    "Of course the server was down that night.",
])
def test_opener_words_inside_normal_sentences_kept(text):
    assert _clean(text) == text
    hits = Scanner().scan(text).hits
    assert not any(h.rule_id == "CHAT-101" for h in hits)


@pytest.mark.parametrize("text", [
    "Certainly! The answer is 42.",
    "Sure thing! The answer is 42.",
    "Of course. The answer is 42.",
    "Great question! The answer is 42.",
])
def test_real_openers_still_removed(text):
    assert _clean(text) == "The answer is 42."


def test_closer_inside_sentence_not_truncated():
    text = "Thanks for reading. Please contact the team if you have any questions."
    assert _clean(text) == text


def test_standalone_closer_sentence_removed():
    text = "The answer is 42. Let me know if you need anything else!"
    assert _clean(text) == "The answer is 42."


# -- knowledge cutoff ------------------------------------------------------------------

def test_language_model_in_technical_prose_kept():
    text = "We trained a small language model on news. It reached 80% accuracy."
    assert _clean(text) == text
    assert TellCategory.KNOWLEDGE_CUTOFF not in Scanner().scan(text).per_category


def test_ai_disclaimer_still_removed():
    text = "As a large language model, I cannot browse. The answer is 42."
    assert _clean(text) == "The answer is 42."


# -- content-kind detection -----------------------------------------------------------

def test_prose_with_code_words_is_not_code():
    text = ("Import duties come from the class of goods. The function of tariffs "
            "is to leverage revenue — a pivotal tool.")
    assert detect_content_kind(text) != ContentKind.CODE
    assert Scanner().scan(text).ai_score > 0
    out = _clean(text)
    assert "leverage" not in out and "—" not in out


def test_real_code_without_path_still_detected():
    code = "import os\nfrom sys import argv\n\ndef main():\n    return argv\n"
    assert detect_content_kind(code) == ContentKind.CODE


# -- dashes ---------------------------------------------------------------------------

def test_cli_flags_in_prose_kept():
    text = "Run the tool with --in-place to edit files."
    assert _clean(text) == text
    assert TellCategory.DASH_OVERUSE not in Scanner().scan(text).per_category


def test_markdown_table_separator_kept():
    text = "| a | b |\n|--|--|\n| 1 | 2 |\n"
    assert _clean(text, "t.md") == text


def test_unspaced_em_dash_cleaned():
    out = _clean("The plan was simple—ship fast—and it worked.")
    assert "—" not in out
    assert out == "The plan was simple, ship fast, and it worked."


def test_period_policy_capitalizes():
    assert _clean("It was fast — really fast.", em_dash_policy="period") == \
        "It was fast. Really fast."


def test_parens_policy_pairs_dashes():
    out = _clean("The tool — a small script — runs offline.", em_dash_policy="parens")
    assert out == "The tool (a small script) runs offline."


def test_markdown_hard_line_break_preserved():
    text = "Line one  \nLine two — with dash.\n"
    assert _clean(text, "b.md").startswith("Line one  \n")


def test_not_just_keeps_sentence_case():
    out = _clean("It's not just a tool, it's a revolution in how teams work.")
    assert out.startswith("It's a tool and")


def test_stats_accumulate_across_segments():
    text = "One — two.\n\n```\ncode\n```\n\nThree — four.\n"
    stats = Cleaner().clean(text, path=Path("d.md")).diff_stats
    assert stats["em_dash_replaced"] == 2


# -- humanizer / LLM ---------------------------------------------------------------------

class _BrokenProvider(LLMProvider):
    name = "broken"

    def rewrite(self, system, prompt, *, max_tokens=4096, temperature=0.7):
        raise RuntimeError("boom")


def test_llm_error_raised_instead_of_silent_fallback():
    with pytest.raises(LLMError):
        Humanizer(Config(use_llm=True), provider=_BrokenProvider()).humanize("Some text.")


def test_llm_fallback_is_opt_in():
    result = Humanizer(Config(use_llm=True, llm_fallback=True),
                       provider=_BrokenProvider()).humanize("Let's delve into it.")
    assert result.mode == "rules"


def test_missing_provider_package_raises(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("no anthropic")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(LLMError, match="pip install"):
        Humanizer(Config(use_llm=True, llm_provider="anthropic")).humanize("Text.")


def test_truncated_llm_output_raises():
    class Truncating(LLMProvider):
        name = "trunc"

        def rewrite(self, system, prompt, *, max_tokens=4096, temperature=0.7):
            raise TruncatedOutputError("hit max_tokens")

    with pytest.raises(TruncatedOutputError):
        Humanizer(Config(use_llm=True), provider=Truncating()).humanize("Text.")


def test_max_tokens_scales_with_input():
    seen = {}

    class Recorder(LLMProvider):
        name = "rec"

        def rewrite(self, system, prompt, *, max_tokens=4096, temperature=0.7):
            seen["max_tokens"] = max_tokens
            return "ok"

    Humanizer(Config(use_llm=True), provider=Recorder()).humanize("word " * 20000)
    assert seen["max_tokens"] > 4096
