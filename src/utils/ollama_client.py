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
        self._chat_models = {"deepseek-r1:8b"}

    def ensure_model(self, model: str) -> bool:
        try:
            self.client.show(model=model)
            return True
        except Exception:  # noqa: BLE001
            return False

    def generate(self, model: str, prompt: str, options: dict[str, Any] | None = None) -> OllamaModelResult:
        try:
            if model in self._chat_models:
                chat_options = {**(options or {})}
                chat_options.pop("num_predict", None)
                chat_response = self.client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    options=chat_options or None,
                )
                output = chat_response.message.content or ""
                tokens: dict[str, Any] = {
                    "prompt": getattr(chat_response, "prompt_eval_count", None),
                    "completion": getattr(chat_response, "eval_count", None),
                }
            else:
                response = self.client.generate(model=model, prompt=prompt, options=options or {})
                output = response.get("response", "")
                tokens = {
                    "prompt": response.get("prompt_eval_count"),
                    "completion": response.get("eval_count"),
                }
        except Exception as exc:  # noqa: BLE001
            raise OllamaUnavailableError(f"Failed to generate with {model}: {exc}") from exc
        return OllamaModelResult(model=model, output=output, tokens=tokens)

    def evaluate_with_judge(self, judge_model: str, article: str, topic: str) -> tuple[bool, str]:
        prompt = (
            "You are a critical reviewer. Decide if the article below stays on topic, is coherent, "
            "and avoids hallucinations. Respond with PASS if it meets all criteria, otherwise respond "
            "with FAIL followed by a short explanation.\n"
            f"Topic: {topic}\n"
            "Article:\n" + article.strip()
        )
        result = self.generate(judge_model, prompt, options={"temperature": 0.1})
        decision_text = result.output.strip()
        decision = decision_text.split()[0].upper() if decision_text else ""
        return decision == "PASS", decision_text


__all__ = ["OllamaRunner", "OllamaUnavailableError", "OllamaModelResult"]
