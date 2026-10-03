"""OpenAI provider for the humanizer layer."""
from __future__ import annotations

import os

from ai_untell.llm.base import LLMError, LLMProvider, TruncatedOutputError

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    name = "openai"
    max_output_tokens = 16384

    def __init__(self, model: str | None = None, api_key: str | None = None):
        try:
            import openai
        except ImportError as exc:
            raise LLMError(
                "The 'openai' package is not installed. "
                "Install it with: pip install 'ai-untell[llm]'"
            ) from exc
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMError("OPENAI_API_KEY is not set.")
        self.model = model or DEFAULT_MODEL
        self.client = openai.OpenAI(api_key=key)

    def rewrite(
        self,
        system: str,
        prompt: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise TruncatedOutputError(
                f"{self.model} stopped at max_tokens={max_tokens}; output is incomplete."
            )
        return choice.message.content or ""
