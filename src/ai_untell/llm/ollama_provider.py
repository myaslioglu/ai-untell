"""Local Ollama provider (no external dependency, plain HTTP)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ai_untell.llm.base import LLMError, LLMProvider, TruncatedOutputError

DEFAULT_MODEL = "llama3.1"
DEFAULT_URL = "http://localhost:11434/api/generate"


class OllamaProvider(LLMProvider):
    name = "ollama"
    max_output_tokens = 32768

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or DEFAULT_MODEL
        self.base_url = base_url or DEFAULT_URL

    def rewrite(
        self,
        system: str,
        prompt: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise LLMError(f"Cannot reach Ollama at {self.base_url}: {exc.reason}") from exc
        if data.get("done_reason") == "length":
            raise TruncatedOutputError(
                f"{self.model} stopped at num_predict={max_tokens}; output is incomplete."
            )
        return data.get("response", "")
