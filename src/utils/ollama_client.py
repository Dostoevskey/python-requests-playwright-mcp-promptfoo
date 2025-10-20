"""Convenience wrapper around the Ollama Python client."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ollama import Client


@dataclass
class OllamaModelResult:
    model: str
    output: str
    tokens: dict[str, Any]


class OllamaUnavailableError(RuntimeError):
    """Raised when Ollama cannot be reached."""


class OllamaRunner:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.client = Client(host=base_url)

    def ensure_model(self, model: str) -> bool:
        try:
            self.client.show(model=model)
            return True
        except Exception:  # noqa: BLE001
            return False

    def generate(self, model: str, prompt: str, options: dict[str, Any] | None = None) -> OllamaModelResult:
        try:
            response = self.client.generate(model=model, prompt=prompt, options=options or {})
        except Exception as exc:  # noqa: BLE001
            raise OllamaUnavailableError(f"Failed to generate with {model}: {exc}") from exc
        return OllamaModelResult(model=model, output=response.get("response", ""), tokens=response.get("eval_count", {}))

    def evaluate_with_judge(self, judge_model: str, article: str, topic: str) -> bool:
        prompt = (
            "You are a critical reviewer. Decide if the article below stays on topic, is coherent, "
            "and avoids hallucinations. Respond with PASS if it meets all criteria, otherwise respond "
            "with FAIL followed by a short explanation.\n"
            f"Topic: {topic}\n"
            "Article:\n" + article.strip()
        )
        result = self.generate(judge_model, prompt, options={"temperature": 0.1})
        decision = result.output.strip().split()[0].upper()
        return decision == "PASS"


__all__ = ["OllamaRunner", "OllamaUnavailableError", "OllamaModelResult"]
