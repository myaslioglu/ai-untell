"""Tests for the humanizer (fake LLM provider + rule fallback)."""
from ai_untell.humanizer import HUMANIZE_SYSTEM_PROMPT, Humanizer
from ai_untell.llm.base import LLMProvider, get_provider
from ai_untell.types import Config


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, response: str):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def rewrite(self, system, prompt, *, max_tokens=4096, temperature=0.7):
        self.calls.append((system, prompt))
        return self.response


def test_rule_fallback_when_no_llm():
    config = Config(use_llm=False)
    result = Humanizer(config).humanize("Let's delve into it \u2014 now.")
    assert result.mode == "rules"
    assert "delve" not in result.cleaned.lower()


def test_llm_path_used_when_configured():
    provider = FakeProvider("Coffee is a drink with a long history.\n")
    config = Config(use_llm=True)
    humanizer = Humanizer(config, provider=provider)
    result = humanizer.humanize("Coffee \u2014 a beverage \u2014 is great.")
    assert result.mode == "llm"
    assert result.cleaned.startswith("Coffee is a drink")
    assert len(provider.calls) == 1
    assert provider.calls[0][0] == HUMANIZE_SYSTEM_PROMPT


def test_prompt_contains_original_text():
    provider = FakeProvider("rewritten")
    humanizer = Humanizer(Config(use_llm=True), provider=provider)
    humanizer.humanize("Some original sentence with delve.")
    _, prompt = provider.calls[0]
    assert "delve" in prompt


def test_fallback_on_provider_error():
    class BrokenProvider(LLMProvider):
        name = "broken"

        def rewrite(self, system, prompt, *, max_tokens=4096, temperature=0.7):
            raise RuntimeError("boom")

    humanizer = Humanizer(Config(use_llm=True), provider=BrokenProvider())
    result = humanizer.humanize("Let's delve into it \u2014 now.")
    assert result.mode == "rules"


def test_postprocess_strips_wrapping_fence():
    provider = FakeProvider("```markdown\nClean text here.\n```")
    humanizer = Humanizer(Config(use_llm=True), provider=provider)
    result = humanizer.humanize("Some text to rewrite.")
    assert result.cleaned == "Clean text here."
    assert "```" not in result.cleaned


def test_invisible_stripped_before_llm():
    provider = FakeProvider("output")
    humanizer = Humanizer(Config(use_llm=True), provider=provider)
    humanizer.humanize("text\u200b with invisible")
    _, prompt = provider.calls[0]
    assert "\u200b" not in prompt


def test_get_provider_unknown_raises():
    try:
        get_provider("nonexistent")
        assert False, "expected ValueError"
    except ValueError:
        pass
