"""Local Ollama provider (no external dependency, plain HTTP)."""
from __future__ import annotations

import json
import urllib.request

from ai_untell.llm.base import LLMProvider

DEFAULT_MODEL = "llama3.1"
DEFAULT_URL = "http://localhost:11434/api/generate"


class OllamaProvider(LLMProvider):
    name = "ollama"

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
        with urllib.request.urlopen(request, timeout=300) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data.get("response", "")
