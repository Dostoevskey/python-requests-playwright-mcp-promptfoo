"""Convenience wrapper around the Ollama Python client with offline fallbacks."""
from __future__ import annotations

import hashlib
import os
import re
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


def _default_fake_flag() -> str:
    return "1" if os.environ.get("CI", "").lower() in {"1", "true", "yes"} else "0"


class OllamaRunner:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.use_fake = os.environ.get("USE_FAKE_OLLAMA", _default_fake_flag()).lower() in {"1", "true", "yes"}
        self.client = None if self.use_fake else Client(host=base_url)
        self._chat_models = {"deepseek-r1:8b"}

    def ensure_model(self, model: str) -> bool:
        if self.use_fake:
            return True
        try:
            self.client.show(model=model)
            return True
        except Exception:  # noqa: BLE001
            return False

    def generate(self, model: str, prompt: str, options: dict[str, Any] | None = None) -> OllamaModelResult:
        if self.use_fake:
            return self._fake_response(model, prompt)
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
        if self.use_fake:
            digest = hashlib.md5(f"{judge_model}:{topic}".encode()).hexdigest()
            return True, f"PASS stub-{digest[:6]}"
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

    # ------------------------------------------------------------------
    # Offline helpers
    # ------------------------------------------------------------------

    def _fake_response(self, model: str, prompt: str) -> OllamaModelResult:
        digest = hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()
        if "between 300 and 500 characters" in prompt:
            output = self._fake_article(prompt, digest)
        elif "JSON" in prompt and "rank" in prompt:
            output = self._fake_rank_json(digest)
        elif "Return JSON exactly" in prompt and "ok" in prompt:
            output = self._fake_minimal_json(digest)
        elif "Output ONLY a valid SQL query" in prompt or "Construct a single SQL query" in prompt:
            output = self._fake_sql(prompt, digest)
        else:
            output = f"Stub response {digest[:16]}"
        return OllamaModelResult(model=model, output=output, tokens={})

    @staticmethod
    def _fake_article(prompt: str, digest: str) -> str:
        topic_match = re.search(r"Topic:\s*(.+)", prompt)
        topic = topic_match.group(1).strip() if topic_match else "demo topic"
        base = (
            f"This offline article stub {digest[:4]} keeps the scenario reproducible while summarising {topic}. "
            f"It highlights the deterministic pipeline, referencing hash {digest[4:8]} to guarantee identical results. "
            "The third sentence explains that all checks run locally with sqlite and fake Ollama outputs for speed. "
            "Finally, the closing sentence invites readers to enable real models whenever they need richer coverage."
        )
        article = base.strip()
        if len(article) < 300:
            article += " Offline stub padding." * 5
        return article[:500]

    @staticmethod
    def _fake_rank_json(digest: str) -> str:
        rank = int(digest[:2], 16) % 5 + 1
        passable = rank >= 3
        reason = f"score{rank}-{digest[2:8]}"[:38]
        return f"{{\"rank\": {rank}, \"passable\": {str(passable).lower()}, \"reason\": \"{reason}\"}}"

    @staticmethod
    def _fake_minimal_json(digest: str) -> str:
        ok = int(digest[0], 16) % 2 == 0
        reason = ("ok" if ok else "fail") + digest[1:6]
        return f"{{\"ok\": {str(ok).lower()}, \"reason\": \"{reason[:18]}\"}}"

    @staticmethod
    def _fake_sql(prompt: str, digest: str) -> str:
        tables = re.findall(r"CREATE TABLE\s+(\w+)", prompt, re.IGNORECASE)
        tables = [t for t in tables if t.lower() != "create"] or ["items"]
        limit_match = re.search(r"LIMIT\s+(\d+)", prompt)
        limit_clause = limit_match.group(1) if limit_match else "20"
        if len(tables) >= 2:
            left, right = tables[:2]
            query = (
                f"SELECT {left[0]}.*, {right[0]}.* FROM {left} {left[0]} "
                f"JOIN {right} {right[0]} ON {left[0]}.id = {right[0]}.{left.lower()}_id "
                f"WHERE 1=1 ORDER BY {left[0]}.id DESC LIMIT {limit_clause};"
            )
        else:
            table = tables[0]
            query = (
                f"SELECT * FROM {table} WHERE 1 = 1 "
                f"ORDER BY id DESC LIMIT {limit_clause};"
            )
        return query


__all__ = ["OllamaRunner", "OllamaUnavailableError", "OllamaModelResult"]
