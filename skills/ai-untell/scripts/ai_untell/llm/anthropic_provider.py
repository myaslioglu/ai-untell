"""Anthropic (Claude) provider for the humanizer layer."""
from __future__ import annotations

import os

from ai_untell.llm.base import LLMError, LLMProvider, TruncatedOutputError

DEFAULT_MODEL = "claude-haiku-4-5"


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    max_output_tokens = 64000

    def __init__(self, model: str | None = None, api_key: str | None = None):
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError(
                "The 'anthropic' package is not installed. "
                "Install it with: pip install 'ai-untell[llm]'"
            ) from exc
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set.")
        self.model = model or DEFAULT_MODEL
        self.client = anthropic.Anthropic(api_key=key)

    def rewrite(
        self,
        system: str,
        prompt: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        if message.stop_reason == "max_tokens":
            raise TruncatedOutputError(
                f"{self.model} stopped at max_tokens={max_tokens}; output is incomplete."
            )
        return "".join(block.text for block in message.content if block.type == "text")
