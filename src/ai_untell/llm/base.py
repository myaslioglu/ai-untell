"""Abstract LLM provider interface used by the humanizer."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Minimal interface: rewrite ``prompt`` under a ``system`` instruction."""

    name: str = "base"

    @abstractmethod
    def rewrite(
        self,
        system: str,
        prompt: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Return the model's rewritten text."""


def get_provider(
    name: str,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMProvider:
    """Factory for LLM providers. Imports SDKs lazily."""
    name = name.lower()
    if name == "anthropic":
        from ai_untell.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model, api_key=api_key)
    if name == "openai":
        from ai_untell.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(model=model, api_key=api_key)
    if name == "ollama":
        from ai_untell.llm.ollama_provider import OllamaProvider

        return OllamaProvider(model=model)
    raise ValueError(f"unknown LLM provider: {name!r}")
